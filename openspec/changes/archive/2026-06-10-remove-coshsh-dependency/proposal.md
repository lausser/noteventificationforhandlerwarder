## Why

The notificationforwarder and eventhandler components currently depend on the `coshsh` Python module for logging setup via `coshsh.util.setup_logging()`. This dependency creates an unnecessary coupling to an external project that serves a different purpose. The logging functionality provided by coshsh is minimal and can be replicated natively within these components, giving us more control and reducing external dependencies.

## What Changes

- Remove the dependency on `coshsh.util.setup_logging()` and implement a native logging setup function
- Remove `coshsh` from runtime and build-time dependency lists
- Keep logfile naming, log format, and `--debug` / `--verbose` behavior compatible with the current tools
- Update both notificationforwarder and eventhandler to use the native implementation

## Capabilities

### New Capabilities
- `native-logging`: Replace coshsh dependency with a native logging implementation that preserves the current logfile naming, formatting, and level selection behavior

### Modified Capabilities
- `runtime-foundation`: Modify the runtime initialization to use native logging instead of coshsh's setup_logging()

## Impact

- Affected code: `notificationforwarder/src/notificationforwarder/baseclass.py`, `eventhandler/src/eventhandler/baseclass.py`, and package metadata in both `pyproject.toml` files
- Affected behavior: No API changes; logging output stays compatible where callers observe logfile naming, format, and log levels
- Affected systems: Both notificationforwarder and eventhandler components
- Dependencies: Removes the need for coshsh as a runtime/build dependency for these two subprojects
