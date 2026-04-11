"""Test session cleanup functionality in dashboard backend.

Tests the cleanup endpoints and automatic cleanup task.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Set test database path before importing backend
os.environ["DASHBOARD_DB_PATH"] = "/tmp/claude/test_dashboard_cleanup.db"

from dashboard.backend import Database


def setup_test_db() -> Database:
    """Create a test database with sample data."""
    # Clean up old test database
    db_path = "/tmp/claude/test_dashboard_cleanup.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    db = Database(db_path)
    return db


def insert_test_session(db: Database, session_id: str, phase: str, hours_ago: int = 0):
    """Insert a test session with heartbeat."""
    # Calculate timestamp
    timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    timestamp_str = timestamp.isoformat()

    # Prepare test data
    raw_state = {
        "current_phase": phase,
        "issue_number": 123,
        "issue_title": f"Test Session {session_id}",
        "issue_type": "feature"
    }

    enriched_data = {
        "session_id": session_id,
        "agent": "test_agent",
        "phase": phase,
        "timestamp": timestamp_str,
        "model": "test-model",
        "context_tokens": 1000,
        "context_percent": 10.0,
        "status": "active" if phase not in ["done", "error"] else phase,
        "raw_state": raw_state,
        "issue_title": f"Test Session {session_id}",
        "issue_type": "feature"
    }

    # Insert session
    db.upsert_session(
        session_id=session_id,
        issue_title=enriched_data["issue_title"],
        issue_type=enriched_data["issue_type"]
    )

    # Insert heartbeat with custom timestamp
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO heartbeats (
            session_id, agent, phase, timestamp, model,
            context_tokens, context_percent, status,
            raw_state, enriched_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        enriched_data["session_id"],
        enriched_data["agent"],
        enriched_data["phase"],
        timestamp_str,
        enriched_data["model"],
        enriched_data["context_tokens"],
        enriched_data["context_percent"],
        enriched_data["status"],
        json.dumps(enriched_data["raw_state"]),
        json.dumps(enriched_data)
    ))

    conn.commit()
    conn.close()


def count_sessions(db: Database) -> int:
    """Count total sessions in database."""
    cursor = db.conn.execute("SELECT COUNT(*) FROM sessions")
    return cursor.fetchone()[0]


def count_heartbeats(db: Database) -> int:
    """Count total heartbeats in database."""
    cursor = db.conn.execute("SELECT COUNT(*) FROM heartbeats")
    return cursor.fetchone()[0]


def test_cleanup_old_sessions():
    """Test cleanup_old_sessions method."""
    print("\n=== Test: cleanup_old_sessions ===")

    db = setup_test_db()

    # Insert test data
    # Old completed sessions (should be deleted)
    insert_test_session(db, "old_done_1", "done", hours_ago=30)
    insert_test_session(db, "old_done_2", "done", hours_ago=48)
    insert_test_session(db, "old_error_1", "error", hours_ago=36)

    # Recent completed sessions (should NOT be deleted)
    insert_test_session(db, "recent_done_1", "done", hours_ago=12)
    insert_test_session(db, "recent_error_1", "error", hours_ago=6)

    # Old active sessions (should NOT be deleted - not completed)
    insert_test_session(db, "old_active_1", "planning", hours_ago=50)

    # Recent active sessions (should NOT be deleted)
    insert_test_session(db, "recent_active_1", "planning", hours_ago=1)

    print(f"Initial sessions: {count_sessions(db)}")
    print(f"Initial heartbeats: {count_heartbeats(db)}")

    # Run cleanup (24 hours threshold)
    result = db.cleanup_old_sessions(max_age_hours=24)

    print(f"\nCleanup result: {result}")
    print(f"Remaining sessions: {count_sessions(db)}")
    print(f"Remaining heartbeats: {count_heartbeats(db)}")

    # Verify
    assert result["sessions_deleted"] == 3, f"Expected 3 sessions deleted, got {result['sessions_deleted']}"
    assert result["heartbeats_deleted"] == 3, f"Expected 3 heartbeats deleted, got {result['heartbeats_deleted']}"
    assert count_sessions(db) == 4, f"Expected 4 remaining sessions, got {count_sessions(db)}"
    assert count_heartbeats(db) == 4, f"Expected 4 remaining heartbeats, got {count_heartbeats(db)}"

    print("✓ Test passed!")


def test_clear_completed_sessions():
    """Test clear_completed_sessions method."""
    print("\n=== Test: clear_completed_sessions ===")

    db = setup_test_db()

    # Insert test data
    # Completed sessions (should be deleted regardless of age)
    insert_test_session(db, "done_1", "done", hours_ago=1)
    insert_test_session(db, "done_2", "done", hours_ago=48)
    insert_test_session(db, "error_1", "error", hours_ago=12)
    insert_test_session(db, "error_2", "error", hours_ago=72)

    # Active sessions (should NOT be deleted)
    insert_test_session(db, "active_1", "planning", hours_ago=1)
    insert_test_session(db, "active_2", "executing", hours_ago=50)

    print(f"Initial sessions: {count_sessions(db)}")
    print(f"Initial heartbeats: {count_heartbeats(db)}")

    # Clear all completed sessions
    result = db.clear_completed_sessions()

    print(f"\nClear result: {result}")
    print(f"Remaining sessions: {count_sessions(db)}")
    print(f"Remaining heartbeats: {count_heartbeats(db)}")

    # Verify
    assert result["sessions_cleared"] == 4, f"Expected 4 sessions cleared, got {result['sessions_cleared']}"
    assert count_sessions(db) == 2, f"Expected 2 remaining sessions, got {count_sessions(db)}"
    assert count_heartbeats(db) == 2, f"Expected 2 remaining heartbeats, got {count_heartbeats(db)}"

    print("✓ Test passed!")


def test_cleanup_no_sessions():
    """Test cleanup when no sessions match criteria."""
    print("\n=== Test: cleanup with no matching sessions ===")

    db = setup_test_db()

    # Insert only active sessions
    insert_test_session(db, "active_1", "planning", hours_ago=1)
    insert_test_session(db, "active_2", "executing", hours_ago=50)

    print(f"Initial sessions: {count_sessions(db)}")

    # Run cleanup (should delete nothing)
    result = db.cleanup_old_sessions(max_age_hours=24)

    print(f"Cleanup result: {result}")

    # Verify nothing was deleted
    assert result["sessions_deleted"] == 0, f"Expected 0 sessions deleted, got {result['sessions_deleted']}"
    assert result["heartbeats_deleted"] == 0, f"Expected 0 heartbeats deleted, got {result['heartbeats_deleted']}"
    assert count_sessions(db) == 2, f"Expected 2 remaining sessions, got {count_sessions(db)}"

    # Clear completed sessions (should also delete nothing)
    result2 = db.clear_completed_sessions()

    print(f"Clear result: {result2}")

    assert result2["sessions_cleared"] == 0, f"Expected 0 sessions cleared, got {result2['sessions_cleared']}"
    assert count_sessions(db) == 2, f"Expected 2 remaining sessions, got {count_sessions(db)}"

    print("✓ Test passed!")


def test_cleanup_stuck_sessions():
    """Test cleanup_stuck_sessions method."""
    print("\n=== Test: cleanup_stuck_sessions ===")

    db = setup_test_db()

    # Stuck sessions: old heartbeat, non-terminal phase (should be deleted)
    insert_test_session(db, "stuck_1", "planning", hours_ago=8)
    insert_test_session(db, "stuck_2", "executing", hours_ago=10)

    # Terminal sessions that are old: should NOT be deleted (phase is done/error)
    insert_test_session(db, "old_done_1", "done", hours_ago=12)
    insert_test_session(db, "old_error_1", "error", hours_ago=15)

    # Recent non-terminal session: should NOT be deleted (fresh heartbeat)
    insert_test_session(db, "recent_active_1", "planning", hours_ago=1)

    print(f"Initial sessions: {count_sessions(db)}")
    print(f"Initial heartbeats: {count_heartbeats(db)}")

    # Run stuck cleanup with 6-hour threshold
    result = db.cleanup_stuck_sessions(max_stale_hours=6)

    print(f"\nCleanup result: {result}")
    print(f"Remaining sessions: {count_sessions(db)}")
    print(f"Remaining heartbeats: {count_heartbeats(db)}")

    # Only stuck_1 and stuck_2 should be removed
    assert result["sessions_deleted"] == 2, f"Expected 2 sessions deleted, got {result['sessions_deleted']}"
    assert result["heartbeats_deleted"] == 2, f"Expected 2 heartbeats deleted, got {result['heartbeats_deleted']}"
    assert len(result["session_ids"]) == 2, f"Expected 2 session IDs in result"
    assert count_sessions(db) == 3, f"Expected 3 remaining sessions, got {count_sessions(db)}"
    assert count_heartbeats(db) == 3, f"Expected 3 remaining heartbeats, got {count_heartbeats(db)}"

    print("✓ Test passed!")


def test_cleanup_stuck_sessions_none_found():
    """Test cleanup_stuck_sessions when no stuck sessions exist."""
    print("\n=== Test: cleanup_stuck_sessions (none found) ===")

    db = setup_test_db()

    # All sessions are either recent or terminal
    insert_test_session(db, "recent_1", "planning", hours_ago=1)
    insert_test_session(db, "done_1", "done", hours_ago=10)

    print(f"Initial sessions: {count_sessions(db)}")

    result = db.cleanup_stuck_sessions(max_stale_hours=6)

    print(f"Cleanup result: {result}")

    assert result["sessions_deleted"] == 0, f"Expected 0 sessions deleted, got {result['sessions_deleted']}"
    assert result["heartbeats_deleted"] == 0, f"Expected 0 heartbeats deleted, got {result['heartbeats_deleted']}"
    assert result["session_ids"] == [], f"Expected empty session_ids list"
    assert count_sessions(db) == 2, f"Expected 2 remaining sessions, got {count_sessions(db)}"

    print("✓ Test passed!")


def test_cleanup_custom_threshold():
    """Test cleanup with custom age threshold."""
    print("\n=== Test: cleanup with custom threshold ===")

    db = setup_test_db()

    # Insert sessions with varying ages
    insert_test_session(db, "done_6h", "done", hours_ago=6)
    insert_test_session(db, "done_13h", "done", hours_ago=13)
    insert_test_session(db, "done_25h", "done", hours_ago=25)

    print(f"Initial sessions: {count_sessions(db)}")

    # Cleanup with 12 hour threshold (should delete only 13h and 25h)
    result = db.cleanup_old_sessions(max_age_hours=12)

    print(f"Cleanup result (12h threshold): {result}")
    print(f"Remaining sessions: {count_sessions(db)}")

    assert result["sessions_deleted"] == 2, f"Expected 2 sessions deleted, got {result['sessions_deleted']}"
    assert count_sessions(db) == 1, f"Expected 1 remaining session, got {count_sessions(db)}"

    print("✓ Test passed!")


if __name__ == "__main__":
    print("Testing Dashboard Cleanup Functionality")
    print("=" * 50)

    try:
        test_cleanup_old_sessions()
        test_clear_completed_sessions()
        test_cleanup_no_sessions()
        test_cleanup_custom_threshold()
        test_cleanup_stuck_sessions()
        test_cleanup_stuck_sessions_none_found()

        print("\n" + "=" * 50)
        print("All tests passed! ✓")

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        # Cleanup test database
        db_path = "/tmp/claude/test_dashboard_cleanup.db"
        if os.path.exists(db_path):
            os.remove(db_path)
            print("\nTest database cleaned up")
