"""Dashboard backend API server.

FastAPI server for receiving heartbeats and serving dashboard UI.
"""

import json
import os
import re
import sqlite3
import asyncio
import sys
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from pathlib import Path

import io
import zipfile

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # requires: pip install aiofiles
from pydantic import BaseModel

from dashboard.enrichers import enrich_heartbeat
from utils.file_logger import get_logger


# Logger
logger = get_logger('dashboard.backend')

# Database path
DB_PATH = os.getenv("DASHBOARD_DB_PATH", "/tmp/claude/dashboard.db")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORCHESTRATE_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "orchestrate.py")
LOG_DIR = Path("/tmp/claude/logs")
SIGNAL_DIR = Path("/tmp/claude/signals")


# Pydantic models
class HeartbeatRequest(BaseModel):
    """Heartbeat API request model."""
    session_id: str
    agent: str
    phase: str
    timestamp: str
    raw_state: Dict[str, Any]


class SessionResponse(BaseModel):
    """Session API response model."""
    id: str
    created_at: str
    updated_at: str
    issue_title: Optional[str] = ""
    issue_type: Optional[str] = "feature"
    status: Optional[str] = "active"
    latest_heartbeat: Optional[Dict[str, Any]] = None
    jira_ticket_id: Optional[str] = None
    jira_ticket_url: Optional[str] = None


class RunRequest(BaseModel):
    """Request to launch a new pipeline run."""
    title: Optional[str] = None
    description: Optional[str] = None
    issue_type: str = "feature"
    jira_ticket: Optional[str] = None
    repo_path: Optional[str] = None
    output_dir: Optional[str] = None
    stages: List[str] = ["design", "develop", "test", "docs"]
    manual_approval: bool = False
    dry_run: bool = False
    debug: bool = False


def _launch_orchestrate(session_id: str, run_request: RunRequest) -> None:
    """Launch orchestrate.py subprocess and capture output to log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file_path = LOG_DIR / f"{session_id}.log"

    cmd = [sys.executable, ORCHESTRATE_SCRIPT, "--session-id", session_id]
    if run_request.title:
        cmd += ["--title", run_request.title]
    if run_request.description:
        cmd += ["--description", run_request.description]
    if run_request.jira_ticket:
        cmd += ["--jira-ticket", run_request.jira_ticket]
    if run_request.repo_path:
        cmd += ["--repo-path", run_request.repo_path]
    if run_request.output_dir:
        cmd += ["--output-dir", run_request.output_dir]
    if run_request.issue_type:
        cmd += ["--issue-type", run_request.issue_type]
    if run_request.dry_run:
        cmd.append("--dry-run")
    if run_request.debug:
        cmd.append("--debug")

    env = os.environ.copy()
    if run_request.manual_approval:
        env["MANUAL_APPROVAL"] = "true"
    else:
        env["MANUAL_APPROVAL"] = "false"

    with open(log_file_path, "w") as log_file:
        subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=PROJECT_ROOT,
            start_new_session=True,
        )
    logger.info(f"Launched orchestrate.py for session {session_id}, log: {log_file_path}")


# Database operations
class Database:
    """Database manager for dashboard data."""

    def __init__(self, db_path: str = DB_PATH):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._ensure_db_dir()
        self._init_schema()
        self._init_connection()

    def _ensure_db_dir(self):
        """Ensure database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _init_connection(self):
        """Initialize persistent database connection for cleanup operations."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_schema(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                issue_title TEXT,
                issue_type TEXT,
                status TEXT DEFAULT 'active'
            )
        """)

        # Heartbeats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                phase TEXT,
                timestamp TIMESTAMP NOT NULL,
                model TEXT,
                context_tokens INTEGER,
                context_percent REAL,
                status TEXT,
                raw_state TEXT,
                enriched_data TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # Index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_timestamp
            ON heartbeats(session_id, timestamp DESC)
        """)

        conn.commit()
        conn.close()

    def upsert_session(self, session_id: str, issue_title: str, issue_type: str):
        """Insert or update a session.

        Args:
            session_id: Session ID
            issue_title: Issue title
            issue_type: Issue type (bug, feature, etc.)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (id, issue_title, issue_type)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP,
                issue_title = excluded.issue_title,
                issue_type = excluded.issue_type
        """, (session_id, issue_title, issue_type))

        conn.commit()
        conn.close()

    def update_session_status(self, session_id: str, status: str) -> bool:
        """Update the status of a session (e.g., 'archived').

        Returns True if a row was updated, False if session not found.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, session_id),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def insert_heartbeat(self, enriched: Dict[str, Any]):
        """Insert an enriched heartbeat.

        Args:
            enriched: Enriched heartbeat dictionary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO heartbeats (
                session_id, agent, phase, timestamp, model,
                context_tokens, context_percent, status,
                raw_state, enriched_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            enriched.get("session_id"),
            enriched.get("agent"),
            enriched.get("phase"),
            enriched.get("timestamp"),
            enriched.get("model"),
            enriched.get("context_tokens"),
            enriched.get("context_percent"),
            enriched.get("status"),
            json.dumps(enriched.get("raw_state", {})),
            json.dumps(enriched)
        ))

        conn.commit()
        conn.close()

    def get_sessions(self, limit: int = 100, include_archived: bool = False) -> List[Dict[str, Any]]:
        """Get all sessions with latest heartbeat.

        Args:
            limit: Maximum number of sessions to return
            include_archived: Whether to include archived sessions (default: False)

        Returns:
            List of session dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where_clause = "" if include_archived else "WHERE s.status != 'archived'"
        cursor.execute(f"""
            SELECT
                s.id, s.created_at, s.updated_at,
                s.issue_title, s.issue_type, s.status,
                h.enriched_data as latest_heartbeat
            FROM sessions s
            LEFT JOIN (
                SELECT session_id, enriched_data,
                       ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY timestamp DESC) as rn
                FROM heartbeats
            ) h ON s.id = h.session_id AND h.rn = 1
            {where_clause}
            ORDER BY s.updated_at DESC
            LIMIT ?
        """, (limit,))

        sessions = []
        for row in cursor.fetchall():
            session = dict(row)
            if session["latest_heartbeat"]:
                session["latest_heartbeat"] = json.loads(session["latest_heartbeat"])
                hb = session["latest_heartbeat"]
                session["jira_ticket_id"] = hb.get("jira_ticket_id") or None
                session["jira_ticket_url"] = hb.get("jira_ticket_url") or None
            sessions.append(session)

        conn.close()
        return sessions

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific session with all heartbeats.

        Args:
            session_id: Session ID

        Returns:
            Session dictionary with heartbeats, or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get session
        cursor.execute("""
            SELECT id, created_at, updated_at, issue_title, issue_type, status
            FROM sessions
            WHERE id = ?
        """, (session_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        session = dict(row)

        # Get heartbeats
        cursor.execute("""
            SELECT enriched_data
            FROM heartbeats
            WHERE session_id = ?
            ORDER BY timestamp ASC
        """, (session_id,))

        heartbeats = [json.loads(row["enriched_data"]) for row in cursor.fetchall()]
        session["heartbeats"] = heartbeats

        conn.close()
        return session

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> dict:
        """Clean up completed sessions older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            dict with counts of deleted sessions and heartbeats
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cutoff_timestamp = cutoff_time.isoformat()

        # Get session IDs to delete
        cursor = self.conn.execute("""
            SELECT DISTINCT session_id FROM heartbeats
            WHERE timestamp < ?
            AND (
                json_extract(raw_state, '$.current_phase') = 'done'
                OR json_extract(raw_state, '$.current_phase') = 'error'
            )
        """, (cutoff_timestamp,))

        session_ids = [row[0] for row in cursor.fetchall()]

        if not session_ids:
            logger.info(f"No sessions to clean up (older than {max_age_hours}h)")
            return {"sessions_deleted": 0, "heartbeats_deleted": 0}

        # Delete heartbeats
        placeholders = ','.join('?' * len(session_ids))
        heartbeats_cursor = self.conn.execute(
            f"DELETE FROM heartbeats WHERE session_id IN ({placeholders})",
            session_ids
        )

        # Delete sessions
        sessions_cursor = self.conn.execute(
            f"DELETE FROM sessions WHERE id IN ({placeholders})",
            session_ids
        )

        self.conn.commit()

        result = {
            "sessions_deleted": sessions_cursor.rowcount,
            "heartbeats_deleted": heartbeats_cursor.rowcount
        }

        logger.info(
            f"Cleaned up {result['sessions_deleted']} sessions "
            f"and {result['heartbeats_deleted']} heartbeats "
            f"(older than {max_age_hours}h)"
        )

        return result

    def cleanup_stuck_sessions(self, max_stale_hours: int = 6) -> dict:
        """Delete sessions that have not received a heartbeat in max_stale_hours
        AND whose phase is not 'done' or 'error' (i.e., stuck/incomplete).

        Args:
            max_stale_hours: Hours without a heartbeat before a session is
                considered stuck

        Returns:
            dict with counts of deleted sessions and heartbeats, and session_ids
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_stale_hours)).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            # Find stuck session IDs: last heartbeat older than cutoff, phase not terminal
            stuck = conn.execute("""
                SELECT s.id
                FROM sessions s
                JOIN (
                    SELECT session_id, MAX(timestamp) AS last_beat
                    FROM heartbeats
                    GROUP BY session_id
                ) h ON s.id = h.session_id
                WHERE h.last_beat < ?
                  AND s.id NOT IN (
                    SELECT DISTINCT session_id FROM heartbeats
                    WHERE json_extract(raw_state, '$.current_phase') IN ('done', 'error')
                  )
            """, (cutoff,)).fetchall()
            stuck_ids = [r[0] for r in stuck]
            if not stuck_ids:
                logger.info(f"No stuck sessions found (stale threshold: {max_stale_hours}h)")
                return {"sessions_deleted": 0, "heartbeats_deleted": 0, "session_ids": []}
            placeholders = ",".join("?" * len(stuck_ids))
            hb_del = conn.execute(
                f"DELETE FROM heartbeats WHERE session_id IN ({placeholders})", stuck_ids
            )
            s_del = conn.execute(
                f"DELETE FROM sessions WHERE id IN ({placeholders})", stuck_ids
            )
            conn.commit()
            result = {
                "sessions_deleted": s_del.rowcount,
                "heartbeats_deleted": hb_del.rowcount,
                "session_ids": stuck_ids,
            }
            logger.info(
                f"Cleaned up {result['sessions_deleted']} stuck sessions "
                f"and {result['heartbeats_deleted']} heartbeats "
                f"(stale threshold: {max_stale_hours}h): {stuck_ids}"
            )
            return result
        finally:
            conn.close()

    def clear_completed_sessions(self) -> dict:
        """Clear all completed or failed sessions (phase='done' or 'error').

        Returns:
            dict with count of cleared sessions and their IDs
        """
        # Get all completed/error session IDs
        cursor = self.conn.execute("""
            SELECT DISTINCT session_id FROM heartbeats
            WHERE json_extract(raw_state, '$.current_phase') IN ('done', 'error')
        """)

        session_ids = [row[0] for row in cursor.fetchall()]

        if not session_ids:
            logger.info("No completed/error sessions to clear")
            return {"sessions_cleared": 0, "session_ids": []}

        # Delete heartbeats for these sessions
        placeholders = ','.join('?' * len(session_ids))
        heartbeats_cursor = self.conn.execute(
            f"DELETE FROM heartbeats WHERE session_id IN ({placeholders})",
            session_ids
        )

        # Delete sessions
        sessions_cursor = self.conn.execute(
            f"DELETE FROM sessions WHERE id IN ({placeholders})",
            session_ids
        )

        self.conn.commit()

        result = {
            "sessions_cleared": sessions_cursor.rowcount,
            "heartbeats_deleted": heartbeats_cursor.rowcount,
            "session_ids": session_ids
        }

        logger.info(
            f"Cleared {result['sessions_cleared']} completed/error sessions "
            f"({result['heartbeats_deleted']} heartbeats): {session_ids}"
        )

        return result


# Global database instance
db = Database()

# Global background task
cleanup_task = None

_SESSION_ID_RE = re.compile(r'^[0-9a-f]{8}$')


def _validate_session_id(session_id: str) -> None:
    """Validate session_id to prevent path traversal attacks."""
    if not _SESSION_ID_RE.fullmatch(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format")


def _get_latest_state(session_id: str) -> dict:
    """Get the latest raw_state from a session's most recent heartbeat."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    heartbeats = session.get("heartbeats", [])
    if not heartbeats:
        raise HTTPException(status_code=404, detail="No heartbeats found for session")
    return heartbeats[-1].get("raw_state", {})


async def periodic_cleanup():
    """Background task to clean up old sessions every 6 hours."""
    while True:
        try:
            # Wait 6 hours
            await asyncio.sleep(6 * 60 * 60)

            # Clean up sessions older than 24 hours
            result = db.cleanup_old_sessions(max_age_hours=24)
            logger.info(f"Automatic cleanup: {result}")

            # Clean up stuck sessions (no heartbeat for 4+ hours, non-terminal)
            stuck_result = db.cleanup_stuck_sessions(max_stale_hours=4)
            logger.info(f"Automatic stuck session cleanup: {stuck_result}")
        except asyncio.CancelledError:
            logger.info("Periodic cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}", exc_info=True)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    global cleanup_task

    # Startup
    logger.info(f"Dashboard backend starting on http://localhost:8080")
    logger.info(f"Database: {db.db_path}")

    # Start background cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("Started automatic cleanup task (runs every 6 hours)")

    yield

    # Shutdown
    logger.info("Dashboard backend shutting down")
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("Stopped automatic cleanup task")


# FastAPI app
app = FastAPI(
    title="Multi-Agent Dashboard",
    description="Real-time monitoring dashboard for Design and Docs agents",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# API routes
@app.post("/api/heartbeat")
async def receive_heartbeat(heartbeat: HeartbeatRequest):
    """Receive and process an agent heartbeat.

    Args:
        heartbeat: Heartbeat data from agent

    Returns:
        Success response
    """
    # Convert to dict
    heartbeat_dict = heartbeat.model_dump()

    # Enrich heartbeat
    enriched = enrich_heartbeat(heartbeat_dict)

    # Upsert session
    db.upsert_session(
        session_id=enriched["session_id"],
        issue_title=enriched.get("issue_title", "Unknown Task"),
        issue_type=enriched.get("issue_type", "feature")
    )

    # Insert heartbeat
    db.insert_heartbeat(enriched)

    logger.debug(
        f"Received heartbeat: session={enriched['session_id']}, "
        f"agent={enriched['agent']}, phase={enriched['phase']}"
    )

    return {"status": "ok"}


@app.get("/api/sessions", response_model=List[SessionResponse])
async def get_sessions(limit: int = 100, include_archived: bool = False):
    sessions = db.get_sessions(limit=limit, include_archived=include_archived)
    logger.debug(f"Retrieved {len(sessions)} sessions")
    return sessions


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific session with all heartbeats.

    Args:
        session_id: Session ID

    Returns:
        Session data with heartbeats

    Raises:
        HTTPException: If session not found
    """
    _validate_session_id(session_id)
    session = db.get_session(session_id)
    if not session:
        logger.warning(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    logger.debug(f"Retrieved session: {session_id}")
    return session


@app.delete("/api/sessions/cleanup")
async def cleanup_completed_sessions(max_age_hours: int = 24):
    """Clean up completed sessions older than specified hours.

    Args:
        max_age_hours: Maximum age in hours for completed sessions (default: 24)

    Returns:
        Number of sessions and heartbeats deleted
    """
    logger.info(f"Manual cleanup requested (max_age_hours={max_age_hours})")
    result = db.cleanup_old_sessions(max_age_hours=max_age_hours)
    return result


@app.delete("/api/sessions/completed")
async def clear_completed_sessions():
    """Clear all sessions with phase='done' or phase='error'.

    Returns:
        dict with sessions_cleared count, heartbeats_deleted count, and session_ids list
    """
    logger.info("Clear all completed/error sessions requested")
    result = db.clear_completed_sessions()
    logger.info(f"Manual session cleanup: {result}")
    return result


@app.delete("/api/sessions/stuck")
async def delete_stuck_sessions(max_stale_hours: int = 6):
    """Delete sessions that have not received a heartbeat in max_stale_hours
    and are not in a terminal phase (done/error).

    Args:
        max_stale_hours: Hours without a heartbeat before a session is
            considered stuck (default: 6)

    Returns:
        dict with sessions_deleted count, heartbeats_deleted count, and session_ids list
    """
    logger.info(f"Stuck session cleanup requested (max_stale_hours={max_stale_hours})")
    result = db.cleanup_stuck_sessions(max_stale_hours=max_stale_hours)
    logger.info(f"Stuck session cleanup: {result}")
    return result


@app.get("/api/health")
async def health():
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/runs")
async def launch_run(run_request: RunRequest, background_tasks: BackgroundTasks):
    """Launch a new pipeline run via the web UI."""
    import uuid
    session_id = str(uuid.uuid4())[:8]

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)

    # Validate: need title or jira_ticket
    if not run_request.title and not run_request.jira_ticket:
        raise HTTPException(status_code=422, detail="Either title or jira_ticket is required")

    # Create session record immediately so dashboard shows it
    db.upsert_session(
        session_id=session_id,
        issue_title=run_request.title or run_request.jira_ticket or "New Run",
        issue_type=run_request.issue_type,
    )

    # Launch subprocess in background
    background_tasks.add_task(_launch_orchestrate, session_id, run_request)

    logger.info(f"New run queued: session_id={session_id}")
    return {"session_id": session_id, "status": "started"}


@app.get("/api/sessions/{session_id}/logs")
async def stream_logs(session_id: str, request: Request):
    """Stream pipeline logs for a session via Server-Sent Events."""
    _validate_session_id(session_id)
    log_file_path = LOG_DIR / f"{session_id}.log"

    async def log_generator():
        # Yield existing lines first
        if log_file_path.exists():
            with open(log_file_path, "r", errors="replace") as f:
                for line in f:
                    yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"

        # Wait up to 10 s for the subprocess to create the log file
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        deadline = asyncio.get_event_loop().time() + 10
        while not log_file_path.exists():
            if asyncio.get_event_loop().time() > deadline:
                yield f"data: {json.dumps({'line': '[log file not created — subprocess may have failed to start]'})}\n\n"
                return
            await asyncio.sleep(0.5)

        # Tail for new lines
        with open(log_file_path, "r", errors="replace") as f:
            f.seek(0, 2)  # seek to end (existing content already yielded above)
            while not await request.is_disconnected():
                line = f.readline()
                if line:
                    yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
                else:
                    await asyncio.sleep(0.2)

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/sessions/{session_id}/approve")
async def approve_session(session_id: str, action: str = "approve"):
    """Signal approval or rejection for a waiting pipeline phase.

    Args:
        session_id: Session ID
        action: 'approve' to continue, 'reject' to stop
    """
    _validate_session_id(session_id)
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="action must be 'approve' or 'reject'")
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    approve_file = SIGNAL_DIR / f"approve-{session_id}"
    approve_file.write_text(action)
    logger.info(f"Approval signal written: session={session_id}, action={action}")
    return {"status": "ok", "action": action}


@app.post("/api/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    """Signal a running pipeline to pause after the current phase."""
    _validate_session_id(session_id)
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    pause_file = SIGNAL_DIR / f"pause-{session_id}"
    pause_file.touch()
    logger.info(f"Pause signal written: session={session_id}")
    return {"status": "ok"}


@app.patch("/api/sessions/{session_id}/archive")
async def archive_session(session_id: str):
    """Archive a session — hides it from the dashboard but preserves all data and artifacts."""
    _validate_session_id(session_id)
    updated = db.update_session_status(session_id, "archived")
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info(f"Session archived: {session_id}")
    return {"status": "archived", "session_id": session_id}


@app.get("/api/sessions/{session_id}/download/all")
async def download_all(session_id: str):
    """Download all artifacts (design, code, tests, docs) as a single zip archive."""
    _validate_session_id(session_id)
    state = _get_latest_state(session_id)

    buf = io.BytesIO()
    files_added = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Design
        design = state.get("design_analysis") or ""
        if design:
            zf.writestr("design/design_analysis.md", design)
            files_added += 1

        impl_plan = state.get("implementation_plan")
        if impl_plan:
            lines = "\n".join(f"- {s}" for s in impl_plan) if isinstance(impl_plan, list) else str(impl_plan)
            zf.writestr("design/implementation_plan.md", lines)
            files_added += 1

        # Code
        code_files = state.get("code_files") or []
        if isinstance(code_files, list):
            for f in code_files:
                path = f.get("path", "unknown.go")
                content = f.get("content", "")
                if content:
                    zf.writestr(f"code/{path}", content)
                    files_added += 1
        else:
            for path, content in (code_files or {}).items():
                if content:
                    zf.writestr(f"code/{path}", content)
                    files_added += 1

        # Tests
        for category, tests in [
            ("unit", state.get("unit_tests") or {}),
            ("integration", state.get("integration_tests") or {}),
            ("e2e", state.get("e2e_tests") or {}),
        ]:
            for path, content in tests.items():
                if content:
                    zf.writestr(f"tests/{category}/{path}", content)
                    files_added += 1

        # Docs
        for fname, key in [
            ("pr_summary.md", "pr_summary"),
            ("release_notes.md", "release_notes"),
            ("pr_description.md", "pr_description"),
        ]:
            content = state.get(key) or ""
            if content:
                zf.writestr(f"docs/{fname}", content)
                files_added += 1

    if files_added == 0:
        raise HTTPException(status_code=404, detail="No artifacts available yet")

    buf.seek(0)
    title = state.get("issue_title", "run").replace(" ", "_")[:40]
    filename = f"{session_id}_{title}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/sessions/{session_id}/download/design")
async def download_design(session_id: str):
    """Download design analysis as a markdown file."""
    _validate_session_id(session_id)
    state = _get_latest_state(session_id)
    content = state.get("design_analysis") or ""
    if not content:
        raise HTTPException(status_code=404, detail="No design analysis available")

    title = state.get("issue_title", "design").replace(" ", "_")[:40]
    filename = f"design_{title}.md"

    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/sessions/{session_id}/download/code")
async def download_code(session_id: str):
    """Download all generated code files as a zip archive."""
    _validate_session_id(session_id)
    state = _get_latest_state(session_id)
    code_files = state.get("code_files") or []

    if not code_files:
        raise HTTPException(status_code=404, detail="No code files available")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if isinstance(code_files, list):
            for f in code_files:
                path = f.get("path", "unknown.go")
                content = f.get("content", "")
                zf.writestr(path, content)
        else:
            for path, content in code_files.items():
                zf.writestr(path, content or "")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="code.zip"'},
    )


@app.get("/api/sessions/{session_id}/download/tests")
async def download_tests(session_id: str):
    """Download all generated test files as a zip archive."""
    _validate_session_id(session_id)
    state = _get_latest_state(session_id)

    unit = state.get("unit_tests") or {}
    integration = state.get("integration_tests") or {}
    e2e = state.get("e2e_tests") or {}

    if not unit and not integration and not e2e:
        raise HTTPException(status_code=404, detail="No test files available")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in unit.items():
            zf.writestr(f"unit/{path}", content or "")
        for path, content in integration.items():
            zf.writestr(f"integration/{path}", content or "")
        for path, content in e2e.items():
            zf.writestr(f"e2e/{path}", content or "")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="tests.zip"'},
    )


@app.get("/api/sessions/{session_id}/download/docs")
async def download_docs(session_id: str):
    """Download documentation files as a zip archive."""
    _validate_session_id(session_id)
    state = _get_latest_state(session_id)

    pr_summary = state.get("pr_summary") or ""
    release_notes = state.get("release_notes") or ""
    pr_description = state.get("pr_description") or ""

    if not pr_summary and not release_notes and not pr_description:
        raise HTTPException(status_code=404, detail="No documentation available")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if pr_summary:
            zf.writestr("pr_summary.md", pr_summary)
        if release_notes:
            zf.writestr("release_notes.md", release_notes)
        if pr_description:
            zf.writestr("pr_description.md", pr_description)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="docs.zip"'},
    )


# Serve frontend — React build (dist/) takes priority over legacy index.html
_dist_dir = os.path.join(os.path.dirname(__file__), "frontend", "dist")
_legacy_index = os.path.join(os.path.dirname(__file__), "frontend", "index.html")

if os.path.exists(_dist_dir):
    # Mount assets directory
    _assets_dir = os.path.join(_dist_dir, "assets")
    if os.path.exists(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the SPA entry point."""
    dist_index = os.path.join(_dist_dir, "index.html")
    if os.path.exists(dist_index):
        with open(dist_index) as f:
            return HTMLResponse(f.read())
    elif os.path.exists(_legacy_index):
        with open(_legacy_index) as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Dashboard</h1><p>Frontend not built. Run: cd dashboard/frontend && npm run build</p>")


_STATIC_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
                      ".webp", ".woff", ".woff2", ".ttf", ".eot", ".css", ".js", ".map"}


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_spa(full_path: str):
    """Serve React SPA for all non-API client-side routes.

    Static files (images, fonts, etc.) placed directly in dist/ are served
    from disk when they exist.  Unknown static-extension paths and API/asset
    prefixes are passed through as 404 so they are not silently replaced with
    the SPA HTML.
    """
    # Don't intercept API or asset-bundle routes
    if full_path.startswith("api/") or full_path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Not found")

    # Serve static files (e.g. /redhat.png) that live directly in dist/
    _, ext = os.path.splitext(full_path)
    if ext.lower() in _STATIC_EXTENSIONS:
        candidate = os.path.join(_dist_dir, full_path)
        if os.path.isfile(candidate):
            import mimetypes
            media_type, _ = mimetypes.guess_type(candidate)
            with open(candidate, "rb") as fh:
                return Response(content=fh.read(), media_type=media_type or "application/octet-stream")
        raise HTTPException(status_code=404, detail="Not found")

    dist_index = os.path.join(_dist_dir, "index.html")
    if os.path.exists(dist_index):
        with open(dist_index) as f:
            return HTMLResponse(f.read())
    elif os.path.exists(_legacy_index):
        with open(_legacy_index) as f:
            return HTMLResponse(f.read())
    raise HTTPException(status_code=404, detail="Frontend not built")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
