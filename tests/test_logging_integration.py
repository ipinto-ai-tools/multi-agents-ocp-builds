"""Test logging integration for all agents."""

import os
import tempfile
from pathlib import Path


def test_design_agent_logging():
    """Test that design_agent has logging configured."""
    from stages.design import logger

    assert logger is not None
    assert logger.name == "stages.design"
    print(f"✓ Design agent logger: {logger.name}")


def test_development_agent_logging():
    """Test that go_k8s_developer has logging configured."""
    from stages.develop import logger

    assert logger is not None
    assert logger.name == "stages.develop"
    print(f"✓ Development agent logger: {logger.name}")


def test_testing_agent_logging():
    """Test that testing_agent has logging configured."""
    from stages.test import logger

    assert logger is not None
    assert logger.name == "stages.test"
    print(f"✓ Testing agent logger: {logger.name}")


def test_docs_agent_logging():
    """Test that docs_agent has logging configured."""
    from stages.docs import logger

    assert logger is not None
    assert logger.name == "stages.docs"
    print(f"✓ Docs agent logger: {logger.name}")


def test_session_logger():
    """Test that session logger can be created."""
    from utils.file_logger import get_session_logger

    session_logger = get_session_logger("test123", "design_agent")
    assert session_logger is not None
    assert "test123" in session_logger.name
    print(f"✓ Session logger: {session_logger.name}")


def test_log_file_creation():
    """Test that log files are created in correct directories."""
    from utils.file_logger import get_logger, LOGS_DIR

    # Create a test logger
    test_logger = get_logger("test_agent", log_file="test/test_agent.log")
    test_logger.info("Test log entry")

    # Check that the log file exists
    log_file = LOGS_DIR / "test" / "test_agent.log"
    assert log_file.exists(), f"Log file not created at {log_file}"
    print(f"✓ Log file created: {log_file}")

    # Clean up
    log_file.unlink()
    log_file.parent.rmdir()


if __name__ == "__main__":
    print("\nTesting logging integration for all agents...\n")

    test_design_agent_logging()
    test_development_agent_logging()
    test_testing_agent_logging()
    test_docs_agent_logging()
    test_session_logger()
    test_log_file_creation()

    print("\n✅ All logging integration tests passed!\n")
