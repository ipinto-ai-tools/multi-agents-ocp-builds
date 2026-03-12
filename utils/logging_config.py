"""Logging configuration for agent testing and debugging.

This module provides centralized logging configuration with support for
debug mode, different output formats, and file logging.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for better readability."""

    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'

    def format(self, record):
        """Format log record with colors."""
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{self.BOLD}{levelname}{self.RESET}"

        # Format the message
        formatted = super().format(record)

        return formatted


def setup_logging(
    debug: bool = False,
    log_file: Optional[Path] = None,
    colored: bool = True
) -> logging.Logger:
    """Setup logging configuration.

    Args:
        debug: Enable debug logging (default: False)
        log_file: Optional path to log file for persistent logging
        colored: Use colored output for console (default: True)

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging(debug=True, log_file=Path("/tmp/test.log"))
        >>> logger.debug("This is a debug message")
        >>> logger.info("This is an info message")
    """
    # Determine log level
    log_level = logging.DEBUG if debug else logging.INFO

    # Create root logger
    logger = logging.getLogger("multi_agent_testing")
    logger.setLevel(log_level)

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if colored and sys.stdout.isatty():
        # Use colored formatter for terminal output
        console_format = "%(levelname)s | %(name)s | %(message)s"
        console_formatter = ColoredFormatter(console_format)
    else:
        # Plain formatter for non-terminal or when colors disabled
        console_format = "[%(levelname)s] %(asctime)s - %(name)s - %(message)s"
        console_formatter = logging.Formatter(console_format, datefmt='%Y-%m-%d %H:%M:%S')

    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler if log file specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)

        # Always use detailed format for file logs
        file_format = "[%(levelname)s] %(asctime)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"
        file_formatter = logging.Formatter(file_format, datefmt='%Y-%m-%d %H:%M:%S')

        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        logger.info(f"Logging to file: {log_file}")

    return logger


def get_agent_logger(agent_name: str) -> logging.Logger:
    """Get logger for specific agent.

    Args:
        agent_name: Name of the agent (e.g., 'design', 'testing', 'docs')

    Returns:
        Logger instance for the agent

    Example:
        >>> logger = get_agent_logger('design')
        >>> logger.info("Design agent starting analysis")
    """
    return logging.getLogger(f"multi_agent_testing.{agent_name}")


def log_agent_start(logger: logging.Logger, agent_name: str, context: dict):
    """Log agent start with context summary.

    Args:
        logger: Logger instance
        agent_name: Name of the agent
        context: Context dictionary passed to agent
    """
    logger.info(f"{'=' * 60}")
    logger.info(f"Starting {agent_name.upper()} Agent")
    logger.info(f"{'=' * 60}")

    # Log key context items
    if "issue_title" in context:
        logger.info(f"Issue: {context['issue_title']}")
    if "issue_type" in context:
        logger.info(f"Type: {context['issue_type']}")

    logger.debug(f"Full context keys: {list(context.keys())}")


def log_agent_complete(logger: logging.Logger, agent_name: str, output: dict):
    """Log agent completion with output summary.

    Args:
        logger: Logger instance
        agent_name: Name of the agent
        output: Output dictionary from agent
    """
    logger.info(f"{'=' * 60}")
    logger.info(f"{agent_name.upper()} Agent Complete")
    logger.info(f"{'=' * 60}")

    # Log key output items
    logger.info(f"Output keys: {list(output.keys())}")

    # Log specific summaries based on agent type
    if agent_name == "design":
        if "impacted_components" in output:
            logger.info(f"Impacted components: {len(output['impacted_components'])}")
        if "risks" in output:
            logger.info(f"Risks identified: {len(output['risks'])}")
        if "acceptance_criteria" in output:
            logger.info(f"Acceptance criteria: {len(output['acceptance_criteria'])}")

    elif agent_name == "testing":
        if "test_specifications" in output:
            logger.info(f"Test specifications: {len(output['test_specifications'])}")
        if "unit_tests" in output:
            logger.info(f"Unit test files: {len(output['unit_tests'])}")
        if "integration_tests" in output:
            logger.info(f"Integration test files: {len(output['integration_tests'])}")
        if "e2e_tests" in output:
            logger.info(f"E2E test files: {len(output['e2e_tests'])}")

    elif agent_name == "docs":
        if "docs_changes" in output:
            logger.info(f"Documentation files: {len(output['docs_changes'])}")


def log_api_call(logger: logging.Logger, model: str, tokens: int, dry_run: bool = False):
    """Log Claude API call details.

    Args:
        logger: Logger instance
        model: Model name (e.g., 'claude-sonnet-4')
        tokens: Token count for the call
        dry_run: Whether this is a dry-run (mocked) call
    """
    mode = "[DRY-RUN]" if dry_run else "[LIVE]"
    logger.debug(f"{mode} Claude API call: model={model}, tokens={tokens}")


def log_error(logger: logging.Logger, agent_name: str, error: Exception):
    """Log agent error with full traceback in debug mode.

    Args:
        logger: Logger instance
        agent_name: Name of the agent
        error: Exception that occurred
    """
    logger.error(f"{agent_name.upper()} Agent Error: {error}")

    if logger.isEnabledFor(logging.DEBUG):
        import traceback
        logger.debug(f"Traceback:\n{traceback.format_exc()}")


def log_heartbeat(logger: logging.Logger, agent: str, phase: str):
    """Log heartbeat emission for dashboard integration.

    Args:
        logger: Logger instance
        agent: Agent name sending heartbeat
        phase: Current phase
    """
    logger.debug(f"Heartbeat: agent={agent}, phase={phase}")


def log_artifact_saved(logger: logging.Logger, file_path: Path):
    """Log artifact save location.

    Args:
        logger: Logger instance
        file_path: Path where artifact was saved
    """
    logger.info(f"Artifact saved: {file_path}")
