## Why

The built-in notificationforwarder and eventhandler plugins are the main integration surface for this repository, but coverage is uneven across modules and failure modes. We need a focused pass that makes the tests explicitly cover every built-in formatter, forwarder, reporter, decider, runner, and logger path so regressions are caught before releases.

## What Changes

- Audit all built-in plugin modules in notificationforwarder and eventhandler, including loggers, formatters, forwarders, reporters, deciders, and runners.
- Add or expand tests so each built-in module has coverage for its normal path, edge cases, and failure behavior.
- Add regression tests for dynamic loading, logger fallback, delivery/spooling failures, discard paths, runner failure propagation, and notification forwarding from eventhandler.
- Tighten test fixtures and assertions where needed so the suite verifies observable behavior, not just import success.

## Capabilities

### New Capabilities
- `builtin-plugin-test-coverage`: comprehensive test coverage for all built-in plugin modules and their failure/edge cases.

### Modified Capabilities
- `developer-experience`: the contributor-facing test requirement expands to explicitly cover all built-in runtime plugins and failure/recovery paths.

## Impact

- Affected code: `notificationforwarder/src/notificationforwarder/**`, `eventhandler/src/eventhandler/**`, and the corresponding test suites.
- Affected behavior: no runtime API changes expected; this change improves confidence in existing behavior and closes coverage gaps.
- Affected systems: OpenSpec planning artifacts for this repo, especially test-focused implementation tasks.
