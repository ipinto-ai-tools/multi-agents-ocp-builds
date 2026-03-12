# Utils Module

This directory contains utility modules for the multi-agent system.

## file_logger.py

Centralized logging configuration for all agents and components.

### Features

- **Dual output**: Logs to both console and file simultaneously
- **Rotating files**: Automatic log rotation at 10MB with 5 backups
- **Smart routing**: Auto-detects component type and creates appropriate log paths
- **Session tracking**: Support for session-specific log files
- **Configurable levels**: Easy control of log verbosity

### Quick Start

```python
from utils.file_logger import get_logger

# Basic usage - auto-detects log path based on name
logger = get_logger('design_agent')
logger.info("Starting design analysis")
logger.warning("Design pattern issue detected")
logger.error("Missing required field")
```

### Log File Locations

Logs are automatically organized by component type:

```
logs/
├── agents/           # Agent logs (design_agent, testing_agent, etc.)
├── dashboard/        # Dashboard component logs
├── tests/            # Test runner logs
├── sessions/         # Session-specific logs
└── [custom]/         # Custom paths if specified
```

### Usage Examples

#### Agent Logger

```python
from utils.file_logger import get_logger

logger = get_logger('design_agent')
logger.info("Analysis complete")
# → logs/agents/design_agent.log
```

#### Dashboard Logger

```python
logger = get_logger('dashboard.backend')
logger.info("Server started")
# → logs/dashboard/dashboard.log
```

#### Session Logger

```python
from utils.file_logger import get_session_logger

logger = get_session_logger('session-123', 'design_agent')
logger.info("Session-specific log entry")
# → logs/sessions/session_session-123_design_agent.log
# Note: No console output for session logs
```

#### Custom Log File

```python
logger = get_logger('my_component', log_file='experiments/test.log')
logger.info("Custom location")
# → logs/experiments/test.log
```

#### Console Only (No File)

```python
logger = get_logger('temp_component', file_output=False)
logger.info("Only in console")
```

#### Change Log Level

```python
from utils.file_logger import get_logger, set_log_level
import logging

logger = get_logger('my_agent', level=logging.DEBUG)
logger.debug("Debug message")

# Change level dynamically
set_log_level('my_agent', logging.WARNING)
```

### Log Levels

Python logging levels (from least to most severe):

- `logging.DEBUG` - Detailed diagnostic information
- `logging.INFO` - General informational messages (default)
- `logging.WARNING` - Warning messages for potentially harmful situations
- `logging.ERROR` - Error messages for serious problems
- `logging.CRITICAL` - Critical messages for very serious errors

### Log Format

All logs use a consistent format:

```
[2026-03-12 18:13:20] [INFO] [design_agent] - Design analysis started
[timestamp]           [level] [component]   - message
```

### Configuration

- **Max file size**: 10MB per log file
- **Backup count**: 5 rotated backups kept
- **Date format**: YYYY-MM-DD HH:MM:SS
- **Propagation**: Disabled to avoid duplicate log entries

### Testing

Run the logger tests:

```bash
uv run pytest tests/test_file_logger.py -v
```

Run the demonstration script:

```bash
PYTHONPATH=. uv run python examples/logger_demo.py
```

### Integration with Agents

Example integration in an agent:

```python
from utils.file_logger import get_logger

class DesignAgent:
    def __init__(self):
        self.logger = get_logger('design_agent')

    def analyze(self, component: str):
        self.logger.info(f"Analyzing component: {component}")
        try:
            # ... analysis logic ...
            self.logger.info(f"Analysis complete: {component}")
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}", exc_info=True)
```

### Best Practices

1. **Use appropriate log levels**:
   - DEBUG: Detailed diagnostic information
   - INFO: Normal operation events
   - WARNING: Unexpected but handled situations
   - ERROR: Error events that might still allow continued execution
   - CRITICAL: Very severe errors that may prevent execution

2. **Include context in messages**:
   ```python
   # Good
   logger.info(f"Processing component: {name}")

   # Better
   logger.info(f"Processing component: {name} with {len(fields)} fields")
   ```

3. **Log exceptions with stack traces**:
   ```python
   try:
       process()
   except Exception as e:
       logger.error(f"Processing failed: {e}", exc_info=True)
   ```

4. **Don't log sensitive information**:
   ```python
   # Bad - logs password
   logger.info(f"Login attempt for {username} with password {password}")

   # Good - no sensitive data
   logger.info(f"Login attempt for {username}")
   ```

5. **Use session loggers for session-specific operations**:
   ```python
   session_logger = get_session_logger(session_id, 'design_agent')
   session_logger.info("Session-specific activity")
   ```
