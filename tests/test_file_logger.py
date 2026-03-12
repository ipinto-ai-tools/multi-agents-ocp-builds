"""
Tests for the centralized file logging configuration.
"""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.file_logger import get_logger, get_session_logger, set_log_level, LOGS_DIR


@pytest.fixture(autouse=True)
def cleanup_loggers():
    """Clean up loggers after each test to avoid handler duplication."""
    yield
    # Clear all handlers from test loggers
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        if logger_name.startswith(('test_', 'design_agent', 'dashboard', 'session')):
            logger = logging.getLogger(logger_name)
            logger.handlers.clear()
            logger.setLevel(logging.NOTSET)


class TestGetLogger:
    """Test the get_logger function."""

    def test_logger_creation_with_defaults(self):
        """Test creating a logger with default settings."""
        logger = get_logger('test_agent')

        assert logger.name == 'test_agent'
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 2  # Console + file

    def test_logger_with_custom_level(self):
        """Test creating a logger with custom log level."""
        logger = get_logger('test_agent_debug', level=logging.DEBUG)

        assert logger.level == logging.DEBUG

    def test_logger_console_only(self):
        """Test creating a console-only logger."""
        logger = get_logger('test_agent_console', file_output=False)

        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        assert not isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)

    def test_logger_file_only(self):
        """Test creating a file-only logger."""
        logger = get_logger('test_agent_file', console_output=False)

        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)

    def test_logger_no_duplicate_handlers(self):
        """Test that calling get_logger twice doesn't add duplicate handlers."""
        logger1 = get_logger('test_agent_dup')
        logger2 = get_logger('test_agent_dup')

        assert logger1 is logger2
        assert len(logger1.handlers) == 2  # Should still be 2, not 4

    def test_agent_log_file_path(self):
        """Test that agent loggers create files in agents/ directory."""
        logger = get_logger('design_agent')

        file_handler = next(
            (h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
            None
        )

        assert file_handler is not None
        expected_path = LOGS_DIR / "agents" / "design_agent.log"
        assert Path(file_handler.baseFilename) == expected_path

    def test_dashboard_log_file_path(self):
        """Test that dashboard loggers create files in dashboard/ directory."""
        logger = get_logger('dashboard.backend')

        file_handler = next(
            (h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
            None
        )

        assert file_handler is not None
        expected_path = LOGS_DIR / "dashboard" / "dashboard.log"
        assert Path(file_handler.baseFilename) == expected_path

    def test_test_log_file_path(self):
        """Test that test loggers create files in tests/ directory."""
        logger = get_logger('test_runner')

        file_handler = next(
            (h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
            None
        )

        assert file_handler is not None
        expected_path = LOGS_DIR / "tests" / "test_runner.log"
        assert Path(file_handler.baseFilename) == expected_path

    def test_custom_log_file_path(self):
        """Test creating a logger with custom log file path."""
        logger = get_logger('test_agent_custom', log_file='custom/my_log.log')

        file_handler = next(
            (h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
            None
        )

        assert file_handler is not None
        expected_path = LOGS_DIR / "custom" / "my_log.log"
        assert Path(file_handler.baseFilename) == expected_path

    def test_log_format(self):
        """Test that log format is correct."""
        logger = get_logger('test_agent_format')

        formatter = logger.handlers[0].formatter
        assert formatter._fmt == '[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s'
        assert formatter.datefmt == '%Y-%m-%d %H:%M:%S'

    def test_rotating_file_handler_config(self):
        """Test that rotating file handler has correct configuration."""
        logger = get_logger('test_agent_rotate')

        file_handler = next(
            (h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
            None
        )

        assert file_handler is not None
        assert file_handler.maxBytes == 10 * 1024 * 1024  # 10MB
        assert file_handler.backupCount == 5

    def test_log_directory_creation(self):
        """Test that log directories are created automatically."""
        logger = get_logger('test_agent_dir')

        file_handler = next(
            (h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
            None
        )

        assert file_handler is not None
        log_dir = Path(file_handler.baseFilename).parent
        assert log_dir.exists()


class TestGetSessionLogger:
    """Test the get_session_logger function."""

    def test_session_logger_creation(self):
        """Test creating a session-specific logger."""
        session_id = 'test_session_123'
        logger = get_session_logger(session_id, 'design_agent')

        assert logger.name == f'session.{session_id}.design_agent'
        assert len(logger.handlers) == 1  # File only
        assert isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)

    def test_session_log_file_path(self):
        """Test that session loggers create files in sessions/ directory."""
        session_id = 'test_session_456'
        logger = get_session_logger(session_id, 'testing_agent')

        file_handler = logger.handlers[0]
        expected_path = LOGS_DIR / "sessions" / f"session_{session_id}_testing_agent.log"
        assert Path(file_handler.baseFilename) == expected_path

    def test_session_logger_no_console_output(self):
        """Test that session loggers don't output to console."""
        logger = get_session_logger('test_session_789', 'docs_agent')

        # Should only have file handler, no console handler
        assert len(logger.handlers) == 1
        assert all(
            not isinstance(h, logging.StreamHandler) or isinstance(h, logging.handlers.RotatingFileHandler)
            for h in logger.handlers
        )


class TestSetLogLevel:
    """Test the set_log_level function."""

    def test_set_log_level_changes_logger_level(self):
        """Test that set_log_level changes the logger's level."""
        logger = get_logger('test_agent_level', level=logging.INFO)
        assert logger.level == logging.INFO

        set_log_level('test_agent_level', logging.DEBUG)

        assert logger.level == logging.DEBUG

    def test_set_log_level_changes_handler_levels(self):
        """Test that set_log_level changes all handler levels."""
        logger = get_logger('test_agent_handlers', level=logging.INFO)

        set_log_level('test_agent_handlers', logging.WARNING)

        for handler in logger.handlers:
            assert handler.level == logging.WARNING


class TestLogging:
    """Test actual logging functionality."""

    def test_logging_to_file(self, tmp_path):
        """Test that logs are actually written to file."""
        # Use a temporary directory for this test
        with patch('utils.file_logger.LOGS_DIR', tmp_path):
            logger = get_logger('test_write_agent')
            test_message = "Test log message"

            logger.info(test_message)

            # Find the log file
            log_files = list(tmp_path.rglob('*.log'))
            assert len(log_files) > 0

            # Read log file and verify message
            log_content = log_files[0].read_text()
            assert test_message in log_content
            assert '[INFO]' in log_content
            assert '[test_write_agent]' in log_content

    def test_logging_different_levels(self, tmp_path):
        """Test logging at different levels."""
        with patch('utils.file_logger.LOGS_DIR', tmp_path):
            logger = get_logger('test_levels_agent', level=logging.DEBUG)

            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")

            # Find the log file
            log_files = list(tmp_path.rglob('*.log'))
            log_content = log_files[0].read_text()

            assert "Debug message" in log_content
            assert "Info message" in log_content
            assert "Warning message" in log_content
            assert "Error message" in log_content
            assert "Critical message" in log_content
