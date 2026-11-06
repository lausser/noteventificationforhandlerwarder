## ADDED Requirements

### Requirement: Native logging implementation exists
Each component (notificationforwarder and eventhandler) SHALL provide its own `setup_logging()` function that does NOT require the coshsh module as a dependency.

#### Scenario: Component initializes logging
- **WHEN** a forwarder or runner instance is created
- **THEN** the component uses its local `setup_logging()` function to configure rotating file logging and console output

### Requirement: Minimal logging implementation
The native `setup_logging()` function SHALL be simple and not implement advanced features:
- No state preservation on the function object
- No runtime logfile switching (`switch_logging`/`restore_logging`)
- No complex handler management beyond file + console

#### Scenario: Logging setup is simple
- **WHEN** `setup_logging()` is called
- **THEN** it creates exactly one rotating file handler and one console handler, returns the logger, and does not store state for later modification

### Requirement: Compatible log file naming
The function SHALL create log files with the same naming convention as coshsh's setup_logging:
- File name derived from the `logfile` parameter
- Logs stored in the `logdir` directory

#### Scenario: Log file creation
- **WHEN** `setup_logging(logdir="/var/log", logfile="notificationforwarder_webhook.log")` is called
- **THEN** the log file is created at `/var/log/notificationforwarder_webhook.log`

### Requirement: Compatible log format
The log format SHALL match the existing format used by notificationforwarder and eventhandler:
- Format: `%(asctime)s %(process)d - %(levelname)s - %(message)s`
- This matches the format string currently used in the baseclass

#### Scenario: Log format verification
- **WHEN** a log entry is written
- **THEN** the format matches `%(asctime)s %(process)d - %(levelname)s - %(message)s`

### Requirement: Log levels respect command-line flags
The function SHALL respect `--debug` and `--verbose` flags:
- `--debug` sets both file and console log levels to DEBUG
- `--verbose` sets console log level to DEBUG (file remains INFO)

#### Scenario: Debug flag sets log level
- **WHEN** `setup_logging()` is called with `txtloglevel=DEBUG, scrnloglevel=DEBUG`
- **THEN** both file and console handlers output DEBUG and above

### Requirement: Formatter logger injection remains visible
Formatter modules SHALL continue to receive the application logger so that module-level logging calls like `logger.debug(...)` are written to the same runtime logfile as the forwarder.

#### Scenario: Formatter logs appear in the runtime log
- **WHEN** a formatter logs a debug message during `format_event()`
- **THEN** the message appears in the forwarder runtime logfile alongside the baseclass and forwarder logs
