#!/usr/bin/env python3
"""Clean the FlowPilot dashboard SQLite database.

Supports deleting all data, specific sessions, stale sessions, or
completed/archived sessions.  Also removes associated log and signal files.

Usage:
    uv run python scripts/clean_dashboard.py --all -y
    uv run python scripts/clean_dashboard.py --session abc12345
    uv run python scripts/clean_dashboard.py --stale 12
    uv run python scripts/clean_dashboard.py --completed --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

LOG_DIR = Path("/tmp/claude/logs")
SIGNAL_DIR = Path("/tmp/claude/signals")


def resolve_db_path(override: str | None = None) -> Path:
    """Resolve the dashboard DB path using the same logic as the backend."""
    if override:
        return Path(os.path.expanduser(override))
    default = str(Path.home() / ".local" / "share" / "flowpilot" / "dashboard.db")
    return Path(os.path.expanduser(os.getenv("DASHBOARD_DB_PATH", default)))


def _remove_file(path: Path, dry_run: bool) -> bool:
    """Remove a file, returning True if it existed (or would have been removed)."""
    if path.exists():
        if not dry_run:
            path.unlink()
        return True
    return False


def _remove_session_files(
    session_id: str, dry_run: bool
) -> Tuple[List[str], List[str]]:
    """Remove log and signal files for a session.

    Returns (removed_logs, removed_signals) lists of file paths.
    """
    if not re.match(r'^[a-zA-Z0-9_\-]+$', session_id):
        return [], []

    removed_logs: List[str] = []
    removed_signals: List[str] = []

    log_file = LOG_DIR / f"{session_id}.log"
    if _remove_file(log_file, dry_run):
        removed_logs.append(str(log_file))

    # Signal files: approve-<id>, pause-<id>
    for prefix in ("approve-", "pause-"):
        signal_file = SIGNAL_DIR / f"{prefix}{session_id}"
        if _remove_file(signal_file, dry_run):
            removed_signals.append(str(signal_file))

    return removed_logs, removed_signals


def _confirm(message: str) -> bool:
    """Ask user for confirmation, return True if confirmed."""
    try:
        answer = input(f"{message} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")


def _tables_exist(cursor: sqlite3.Cursor) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('sessions', 'heartbeats')"
    )
    found = {row[0] for row in cursor.fetchall()}
    return 'sessions' in found and 'heartbeats' in found


def _delete_sessions_batch(
    cursor: sqlite3.Cursor, session_ids: list[str]
) -> tuple[int, int]:
    """Delete sessions and their heartbeats in batch.

    Returns (sessions_deleted, heartbeats_deleted).
    """
    if not session_ids:
        return 0, 0
    placeholders = ",".join("?" * len(session_ids))
    cursor.execute(
        f"DELETE FROM heartbeats WHERE session_id IN ({placeholders})",
        session_ids,
    )
    heartbeats_deleted = cursor.rowcount
    cursor.execute(
        f"DELETE FROM sessions WHERE id IN ({placeholders})",
        session_ids,
    )
    sessions_deleted = cursor.rowcount
    return sessions_deleted, heartbeats_deleted


def clean_all(
    db_path: Path, *, dry_run: bool, skip_confirm: bool
) -> None:
    """Delete ALL sessions, heartbeats, and associated files."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        if not _tables_exist(cursor):
            print("Database has no dashboard tables -- nothing to clean.")
            return

        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM heartbeats")
        heartbeat_count = cursor.fetchone()[0]

        # Collect session IDs for file cleanup
        cursor.execute("SELECT id FROM sessions")
        session_ids = [row[0] for row in cursor.fetchall()]

        action = "Would delete" if dry_run else "Deleting"
        print(f"{action}: {session_count} session(s), {heartbeat_count} heartbeat(s)")

        if not dry_run:
            if not skip_confirm and not _confirm("Delete ALL dashboard data?"):
                print("Aborted.")
                return

            _delete_sessions_batch(cursor, session_ids)
            conn.commit()
    finally:
        conn.close()

    all_logs: List[str] = []
    all_signals: List[str] = []
    for sid in session_ids:
        logs, signals = _remove_session_files(sid, dry_run)
        all_logs.extend(logs)
        all_signals.extend(signals)

    _print_summary(
        session_count, heartbeat_count, all_logs, all_signals, dry_run=dry_run
    )


def clean_session(
    db_path: Path, session_id: str, *, dry_run: bool, skip_confirm: bool
) -> None:
    """Delete a specific session by ID."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        if not _tables_exist(cursor):
            print("Database has no dashboard tables -- nothing to clean.")
            return

        cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            print(f"Session '{session_id}' not found in database.")
            sys.exit(1)

        cursor.execute(
            "SELECT COUNT(*) FROM heartbeats WHERE session_id = ?", (session_id,)
        )
        heartbeat_count = cursor.fetchone()[0]

        action = "Would delete" if dry_run else "Deleting"
        print(f"{action}: session '{session_id}' with {heartbeat_count} heartbeat(s)")

        if not dry_run:
            if not skip_confirm and not _confirm(
                f"Delete session '{session_id}'?"
            ):
                print("Aborted.")
                return

            cursor.execute(
                "DELETE FROM heartbeats WHERE session_id = ?", (session_id,)
            )
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
    finally:
        conn.close()

    logs, signals = _remove_session_files(session_id, dry_run)
    _print_summary(1, heartbeat_count, logs, signals, dry_run=dry_run)


def clean_stale(
    db_path: Path, hours: int, *, dry_run: bool, skip_confirm: bool
) -> None:
    """Delete sessions with no heartbeat in the last N hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        if not _tables_exist(cursor):
            print("Database has no dashboard tables -- nothing to clean.")
            return

        # Sessions whose most recent heartbeat is older than cutoff
        cursor.execute(
            """
            SELECT s.id
            FROM sessions s
            LEFT JOIN (
                SELECT session_id, MAX(timestamp) AS last_beat
                FROM heartbeats
                GROUP BY session_id
            ) h ON s.id = h.session_id
            WHERE h.last_beat IS NULL OR h.last_beat < ?
            """,
            (cutoff,),
        )
        session_ids = [row[0] for row in cursor.fetchall()]

        if not session_ids:
            print(f"No stale sessions found (threshold: {hours} hours).")
            return

        # Count heartbeats
        placeholders = ",".join("?" * len(session_ids))
        cursor.execute(
            f"SELECT COUNT(*) FROM heartbeats WHERE session_id IN ({placeholders})",
            session_ids,
        )
        heartbeat_count = cursor.fetchone()[0]

        action = "Would delete" if dry_run else "Deleting"
        print(
            f"{action}: {len(session_ids)} stale session(s) "
            f"(no heartbeat in {hours}h), {heartbeat_count} heartbeat(s)"
        )
        for sid in session_ids:
            print(f"  - {sid}")

        if not dry_run:
            if not skip_confirm and not _confirm("Proceed with deletion?"):
                print("Aborted.")
                return

            _delete_sessions_batch(cursor, session_ids)
            conn.commit()
    finally:
        conn.close()

    all_logs: List[str] = []
    all_signals: List[str] = []
    for sid in session_ids:
        logs, signals = _remove_session_files(sid, dry_run)
        all_logs.extend(logs)
        all_signals.extend(signals)

    _print_summary(
        len(session_ids), heartbeat_count, all_logs, all_signals, dry_run=dry_run
    )


def clean_completed(
    db_path: Path, *, dry_run: bool, skip_confirm: bool
) -> None:
    """Delete all completed or archived sessions."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        if not _tables_exist(cursor):
            print("Database has no dashboard tables -- nothing to clean.")
            return

        cursor.execute(
            "SELECT id FROM sessions WHERE status IN ('completed', 'archived', 'failed')"
        )
        session_ids = [row[0] for row in cursor.fetchall()]

        if not session_ids:
            print("No completed/archived/failed sessions found.")
            return

        placeholders = ",".join("?" * len(session_ids))
        cursor.execute(
            f"SELECT COUNT(*) FROM heartbeats WHERE session_id IN ({placeholders})",
            session_ids,
        )
        heartbeat_count = cursor.fetchone()[0]

        action = "Would delete" if dry_run else "Deleting"
        print(
            f"{action}: {len(session_ids)} completed/archived/failed session(s), "
            f"{heartbeat_count} heartbeat(s)"
        )
        for sid in session_ids:
            print(f"  - {sid}")

        if not dry_run:
            if not skip_confirm and not _confirm("Proceed with deletion?"):
                print("Aborted.")
                return

            _delete_sessions_batch(cursor, session_ids)
            conn.commit()
    finally:
        conn.close()

    all_logs: List[str] = []
    all_signals: List[str] = []
    for sid in session_ids:
        logs, signals = _remove_session_files(sid, dry_run)
        all_logs.extend(logs)
        all_signals.extend(signals)

    _print_summary(
        len(session_ids), heartbeat_count, all_logs, all_signals, dry_run=dry_run
    )


def _print_summary(
    sessions: int,
    heartbeats: int,
    logs: List[str],
    signals: List[str],
    *,
    dry_run: bool,
) -> None:
    """Print a summary of what was (or would be) deleted."""
    prefix = "[DRY RUN] Would have deleted" if dry_run else "Deleted"
    print(f"\n{prefix}:")
    print(f"  Sessions:   {sessions}")
    print(f"  Heartbeats: {heartbeats}")
    print(f"  Log files:  {len(logs)}")
    if logs:
        for path in logs:
            print(f"    - {path}")
    print(f"  Signal files: {len(signals)}")
    if signals:
        for path in signals:
            print(f"    - {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean the FlowPilot dashboard SQLite database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  uv run python scripts/clean_dashboard.py --all -y\n"
            "  uv run python scripts/clean_dashboard.py --session abc12345\n"
            "  uv run python scripts/clean_dashboard.py --stale 12\n"
            "  uv run python scripts/clean_dashboard.py --completed --dry-run\n"
        ),
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--all",
        action="store_true",
        help="Delete ALL sessions, heartbeats, and associated files",
    )
    mode.add_argument(
        "--session",
        metavar="SESSION_ID",
        help="Delete a specific session by ID",
    )
    mode.add_argument(
        "--stale",
        metavar="HOURS",
        type=int,
        nargs="?",
        const=6,
        help="Delete sessions with no heartbeat in the last N hours (default: 6)",
    )
    mode.add_argument(
        "--completed",
        action="store_true",
        help="Delete all completed/archived/failed sessions",
    )

    parser.add_argument(
        "--db-path",
        metavar="PATH",
        help=(
            "Override DB path (otherwise uses DASHBOARD_DB_PATH env var "
            "or ~/.local/share/flowpilot/dashboard.db)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    db_path = resolve_db_path(args.db_path)

    if not db_path.exists():
        print(f"Database not found at {db_path} -- nothing to clean.")
        sys.exit(0)

    print(f"Database: {db_path}")
    if args.dry_run:
        print("(dry-run mode -- no changes will be made)\n")

    if args.all:
        clean_all(db_path, dry_run=args.dry_run, skip_confirm=args.yes)
    elif args.session:
        clean_session(
            db_path, args.session, dry_run=args.dry_run, skip_confirm=args.yes
        )
    elif args.stale is not None:
        clean_stale(
            db_path, args.stale, dry_run=args.dry_run, skip_confirm=args.yes
        )
    elif args.completed:
        clean_completed(db_path, dry_run=args.dry_run, skip_confirm=args.yes)


if __name__ == "__main__":
    main()
