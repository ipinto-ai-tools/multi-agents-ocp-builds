"""
Centralized file logging configuration for multi-agent system.

Provides consistent logging across all agents and components with:
- Console and file output
- Rotating file handlers
- Per-agent log files
- Configurable log levels
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from tools.output_sanitizer import SanitizingFilter

# Base logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"


def get_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    console_output: bool = True,
    file_output: bool = True,
) -> logging.Logger:
    """
    Get a configured logger for an agent or component.

    Args:
        name: Logger name (e.g., 'design_agent', 'dashboard.backend')
        log_file: Optional specific log file path (relative to logs/)
        level: Logging level (default: INFO)
        console_output: Whether to log to console (default: True)
        file_output: Whether to log to file (default: True)

    Returns:
        Configured logger instance

    Example:
         logger = get_logger('design_agent')
         logger.info("Starting design analysis")
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(SanitizingFilter())
        logger.addHandler(console_handler)

    # File handler
    if file_output:
        if log_file is None:
            # Auto-generate log file path based on logger name
            component = name.split('.')[0]  # e.g., 'design_agent' from 'design_agent.validator'

            if 'agent' in component:
                log_dir = LOGS_DIR / "agents"
            elif 'dashboard' in component:
                log_dir = LOGS_DIR / "dashboard"
            elif 'test' in component:
                log_dir = LOGS_DIR / "tests"
            else:
                log_dir = LOGS_DIR

            log_file = log_dir / f"{component}.log"
        else:
            log_file = LOGS_DIR / log_file

        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler (10MB max, keep 5 backups)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SanitizingFilter())
        logger.addHandler(file_handler)

    return logger


def get_session_logger(session_id: str, agent_name: str) -> logging.Logger:
    """
    Get a logger for a specific session with session-specific log file.

    Args:
        session_id: Unique session identifier
        agent_name: Name of the agent (design, development, testing, docs)

    Returns:
        Logger configured to write to session-specific file

    Example:
         logger = get_session_logger('abc123', 'design_agent')
         logger.info("Session-specific log entry")
    """
    logger_name = f"session.{session_id}.{agent_name}"
    log_file = f"sessions/session_{session_id}_{agent_name}.log"

    return get_logger(
        name=logger_name,
        log_file=log_file,
        console_output=False,  # Session logs only to file
        file_output=True
    )


def set_log_level(logger_name: str, level: int):
    """
    Change log level for an existing logger.

    Args:
        logger_name: Name of the logger
        level: New log level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
         set_log_level('design_agent', logging.DEBUG)
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
