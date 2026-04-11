"""
Demonstration of the centralized file logger.

This script shows how to use the file logger in different scenarios.
"""

import logging
from utils.file_logger import get_logger, get_session_logger, set_log_level


def demo_basic_logger():
    """Demonstrate basic logger usage."""
    print("\n=== Basic Logger Demo ===\n")

    logger = get_logger('design_agent')
    logger.info("Design agent initialized")
    logger.info("Starting design analysis for component: UserService")
    logger.warning("Design pattern mismatch detected")
    logger.error("Missing required field in design spec")

    print("✓ Logs written to: logs/stages/design.log")


def demo_dashboard_logger():
    """Demonstrate dashboard logger with subcomponents."""
    print("\n=== Dashboard Logger Demo ===\n")

    backend_logger = get_logger('dashboard.backend')
    frontend_logger = get_logger('dashboard.frontend')

    backend_logger.info("Backend server started on port 8000")
    backend_logger.debug("Processing request: GET /api/agents")

    frontend_logger.info("Frontend app initialized")
    frontend_logger.warning("Slow rendering detected: 250ms")

    print("✓ Logs written to: logs/dashboard/dashboard.log")


def demo_session_logger():
    """Demonstrate session-specific logging."""
    print("\n=== Session Logger Demo ===\n")

    session_id = "abc-123-def-456"

    design_logger = get_session_logger(session_id, 'design_agent')
    testing_logger = get_session_logger(session_id, 'testing_agent')

    design_logger.info(f"Session {session_id}: Design phase started")
    design_logger.info("Analyzing 5 components")

    testing_logger.info(f"Session {session_id}: Testing phase started")
    testing_logger.info("Running unit tests")

    print(f"✓ Session logs written to: logs/sessions/session_{session_id}_*.log")


def demo_log_levels():
    """Demonstrate different log levels and filtering."""
    print("\n=== Log Level Demo ===\n")

    # Create logger with DEBUG level
    logger = get_logger('test_component', level=logging.DEBUG)

    logger.debug("Debug message: Variable x = 42")
    logger.info("Info message: Processing started")
    logger.warning("Warning message: Deprecated API used")
    logger.error("Error message: Connection failed")
    logger.critical("Critical message: System failure")

    print("✓ All levels logged to: logs/test_component.log")

    # Change log level dynamically
    set_log_level('test_component', logging.WARNING)
    logger.info("This INFO message won't be logged after level change")
    logger.warning("This WARNING message will be logged")

    print("✓ Log level changed to WARNING")


def demo_custom_log_file():
    """Demonstrate custom log file path."""
    print("\n=== Custom Log File Demo ===\n")

    logger = get_logger(
        'custom_component',
        log_file='experiments/custom.log'
    )

    logger.info("Custom log file example")
    logger.info("This goes to a custom directory")

    print("✓ Logs written to: logs/experiments/custom.log")


def demo_console_only():
    """Demonstrate console-only logging."""
    print("\n=== Console-Only Logger Demo ===\n")

    logger = get_logger(
        'console_agent',
        file_output=False
    )

    logger.info("This only appears in console, not in any file")

    print("✓ Console-only logger (no file created)")


if __name__ == '__main__':
    print("=" * 60)
    print("File Logger Demonstration")
    print("=" * 60)

    demo_basic_logger()
    demo_dashboard_logger()
    demo_session_logger()
    demo_log_levels()
    demo_custom_log_file()
    demo_console_only()

    print("\n" + "=" * 60)
    print("Demo complete! Check the logs/ directory for output.")
    print("=" * 60)
