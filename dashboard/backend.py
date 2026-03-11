"""Dashboard backend API server.

FastAPI server for receiving heartbeats and serving dashboard UI.
"""

import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dashboard.enrichers import enrich_heartbeat


# Database path
DB_PATH = os.getenv("DASHBOARD_DB_PATH", "/tmp/claude/dashboard.db")


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
    issue_title: str
    issue_type: str
    status: str
    latest_heartbeat: Optional[Dict[str, Any]] = None


# Database operations
class Database:
    """Database manager for dashboard data."""

    def __init__(self, db_path: str = DB_PATH):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_schema()

    def _ensure_db_dir(self):
        """Ensure database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

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

    def insert_heartbeat(self, enriched: Dict[str, Any]):
        """Insert an enriched heartbeat.

        Args:
            enriched: Enriched heartbeat dictionary
        """
        import json

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

    def get_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all sessions with latest heartbeat.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session dictionaries
        """
        import json

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
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
            ORDER BY s.updated_at DESC
            LIMIT ?
        """, (limit,))

        sessions = []
        for row in cursor.fetchall():
            session = dict(row)
            if session["latest_heartbeat"]:
                session["latest_heartbeat"] = json.loads(session["latest_heartbeat"])
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
        import json

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


# Global database instance
db = Database()


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    print(f"Dashboard backend starting on http://localhost:8080")
    print(f"Database: {db.db_path}")
    yield
    # Shutdown
    print("Dashboard backend shutting down")


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
    allow_credentials=True,
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

    return {"status": "ok"}


@app.get("/api/sessions", response_model=List[SessionResponse])
async def get_sessions(limit: int = 100):
    """Get all sessions with latest heartbeat.

    Args:
        limit: Maximum sessions to return

    Returns:
        List of sessions
    """
    sessions = db.get_sessions(limit=limit)
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
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/api/health")
async def health():
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Serve frontend
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the dashboard frontend.

    Returns:
        HTML response
    """
    frontend_path = os.path.join(
        os.path.dirname(__file__),
        "frontend",
        "index.html"
    )

    if os.path.exists(frontend_path):
        with open(frontend_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="""
        <html>
            <head><title>Dashboard</title></head>
            <body>
                <h1>Multi-Agent Dashboard</h1>
                <p>Frontend not found. API is available at /api/sessions</p>
            </body>
        </html>
        """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
