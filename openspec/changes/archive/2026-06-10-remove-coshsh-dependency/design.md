## Context

The notificationforwarder and eventhandler components currently use `coshsh.util.setup_logging()` for log initialization. This function is part of the coshsh project, which is a separate library for OMD monitoring system utilities. While the coshsh module is commonly available in OMD environments, it creates an unnecessary dependency.

Current implementation in `notificationforwarder/src/notificationforwarder/baseclass.py` (lines 48-56):
```python
setup_logging(
    logdir=runtime_config.log_dir,
    logfile=runtime_config.logger_name + ".log",
    scrnloglevel=runtime_config.screen_log_level,
    txtloglevel=runtime_config.text_log_level,
    format="%(asctime)s %(process)d - %(levelname)s - %(message)s",
    backup_count=runtime_config.backup_count,
)
```

**Simplification**: We do NOT need coshsh's advanced logging features like `switch_logging()`/`restore_logging()` for runtime logfile changes. We only need the minimal behavior the tools already expose to users:
- Maintain the current log file naming convention (`notificationforwarder_<name>.log`, `eventhandler_<name>.log`)
- Use the current log format (`%(asctime)s %(process)d - %(levelname)s - %(message)s`)
- Respect `--debug` and `--verbose` command-line flags for log levels

## Goals / Non-Goals

**Goals:**
- Replace coshsh dependency with a minimal native logging implementation
- Maintain compatible log file naming, format, and level selection for existing deployments
- Implement simple, straightforward logging setup without advanced features
- Make the codebase more self-contained and reduce external dependencies

**Non-Goals:**
- Implementing advanced logging features (runtime logfile switching, multiple handlers, state preservation)
- Changing log file naming conventions (e.g., `notificationforwarder_<name>.log`)
- Changing log format (keep `%(asctime)s %(process)d - %(levelname)s - %(message)s`)
- Adding new logging features beyond basic file/console logging and the existing log-level behavior
- Supporting non-file logging (e.g., syslog, HTTP endpoints)
- Preserving logging state on the function object (not needed for our use case)

## Decisions

1. **Minimal native logging function**: Create simple `setup_logging()` functions that:
   - Add a console handler for stderr output
   - Use the same log format as coshsh
   - Return the logger instance for use by the calling code

2. **Simplified function signature**: Keep the same parameters for minimal code changes, but don't implement state preservation:
   - `logdir`: Log directory path
   - `logfile`: Log filename
   - `scrnloglevel`: Console log level (INFO or DEBUG based on `--verbose`/`--debug`)
   - `txtloglevel`: File log level (INFO or DEBUG based on `--verbose`/`--debug`)
   - `format`: Log format string (keep coshsh's default)
   - `backup_count`: Number of backup files (default: 3 to match existing behavior)

3. **Simple implementation**: Use Python's standard logging module directly:
   ```python
   logger = logging.getLogger(logger_name)
   logger.setLevel(logging.DEBUG)
   # Add handlers, return logger
   ```

4. **Implement in both components separately**: Each subproject (notificationforwarder, eventhandler) gets its own minimal `util.setup_logging()` function

5. **Preserve logger injection contract**: The loader must continue to inject the application logger into the formatter/logger module namespace so module-level `logger.debug(...)` calls in formatters and loggers remain visible in the shared runtime logfile

6. **No state preservation**: Don't store logging state as function attributes - we don't need `switch_logging()`/`restore_logging()` features

## Risks / Trade-offs

- **Risk**: Minor differences in backup count (coshsh uses 2, existing code may expect 3)
  - **Mitigation**: The existing code already uses `backup_count=3` (from RuntimeConfig), so we'll keep that

- **Risk**: Need to update all imports across the codebase
  - **Mitigation**: Simple import path changes; low risk

- **Risk**: Existing code that imports `setup_logging` from `coshsh.util` elsewhere in the codebase
  - **Mitigation**: Search and replace to use local `notificationforwarder.util` or `eventhandler.util`

## Migration Plan

1. Create `notificationforwarder/util.py` with simple `setup_logging()` function
2. Create `eventhandler/util.py` with simple `setup_logging()` function
3. Update `notificationforwarder/src/notificationforwarder/baseclass.py` to import from local util
4. Update `eventhandler/src/eventhandler/baseclass.py` to import from local util
5. Update any other modules that import `setup_logging` from coshsh
6. Run existing tests to verify no behavior changes
7. Update documentation to reflect new dependency status

## Open Questions

None. The implementation is straightforward and doesn't require advanced logging features.
