#!/usr/bin/env python3
"""Manual test script for cleanup API endpoints.

This script demonstrates how to use the cleanup API endpoints.
Run the dashboard backend first: uv run python dashboard/backend.py

Then in another terminal run: PYTHONPATH=. uv run python examples/test_cleanup_api.py
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8080"


def test_health():
    """Test health endpoint."""
    print("\n=== Testing health endpoint ===")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def get_sessions():
    """Get all sessions."""
    print("\n=== Getting all sessions ===")
    response = requests.get(f"{BASE_URL}/api/sessions")
    print(f"Status: {response.status_code}")
    sessions = response.json()
    print(f"Total sessions: {len(sessions)}")
    for session in sessions:
        print(f"  - {session['id']}: {session.get('issue_title', 'N/A')} (phase: {session.get('latest_heartbeat', {}).get('phase', 'unknown')})")
    return sessions


def cleanup_old_sessions(max_age_hours=24):
    """Cleanup old completed sessions."""
    print(f"\n=== Cleaning up sessions older than {max_age_hours}h ===")
    response = requests.delete(f"{BASE_URL}/api/sessions/cleanup?max_age_hours={max_age_hours}")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Result: {json.dumps(result, indent=2)}")
    return result


def clear_completed_sessions():
    """Clear all completed sessions."""
    print("\n=== Clearing all completed sessions ===")
    response = requests.delete(f"{BASE_URL}/api/sessions/completed")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Result: {json.dumps(result, indent=2)}")
    return result


def send_test_heartbeat(session_id, phase="done", agent="test_agent"):
    """Send a test heartbeat."""
    print(f"\n=== Sending test heartbeat (session={session_id}, phase={phase}) ===")
    heartbeat = {
        "session_id": session_id,
        "agent": agent,
        "phase": phase,
        "timestamp": datetime.now().isoformat(),
        "raw_state": {
            "phase": phase,
            "issue_number": 123,
            "issue_title": f"Test Session {session_id}",
            "issue_type": "feature"
        }
    }
    response = requests.post(f"{BASE_URL}/api/heartbeat", json=heartbeat)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def main():
    """Run manual API tests."""
    print("Dashboard Cleanup API Test")
    print("=" * 60)
    print("Make sure the dashboard backend is running:")
    print("  uv run python dashboard/backend.py")
    print("=" * 60)

    try:
        # Test health
        if not test_health():
            print("\n❌ Dashboard backend is not running!")
            print("Start it with: uv run python dashboard/backend.py")
            return

        # Get initial state
        print("\n--- Initial State ---")
        initial_sessions = get_sessions()

        # Send some test heartbeats
        print("\n--- Sending Test Heartbeats ---")
        send_test_heartbeat("test_session_1", "done")
        send_test_heartbeat("test_session_2", "error")
        send_test_heartbeat("test_session_3", "planning")

        # Get state after heartbeats
        print("\n--- State After Test Heartbeats ---")
        get_sessions()

        # Test cleanup with 1 hour threshold (won't delete recent test data)
        print("\n--- Testing Cleanup (1h threshold) ---")
        cleanup_result = cleanup_old_sessions(max_age_hours=1)

        # Get state after cleanup
        print("\n--- State After Cleanup ---")
        get_sessions()

        # Test clear completed sessions
        print("\n--- Testing Clear Completed Sessions ---")
        clear_result = clear_completed_sessions()

        # Get final state
        print("\n--- Final State ---")
        final_sessions = get_sessions()

        # Summary
        print("\n" + "=" * 60)
        print("Test Summary:")
        print(f"  Initial sessions: {len(initial_sessions)}")
        print(f"  Sessions after test heartbeats: {len(initial_sessions) + 3}")
        print(f"  Sessions cleaned up (1h): {cleanup_result.get('sessions_deleted', 0)}")
        print(f"  Completed sessions cleared: {clear_result.get('sessions_cleared', 0)}")
        print(f"  Final sessions: {len(final_sessions)}")
        print("=" * 60)
        print("\n✅ All API tests completed successfully!")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to dashboard backend!")
        print("Start it with: uv run python dashboard/backend.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
