# Proposal

## Why

The notificationforwarder lint baseline contains 119 findings, including a real RabbitMQ disconnect typo hidden by exception handling. CI currently does not enforce lint, so future undefined-name errors can escape the existing checks.

## What Changes

- Fix RabbitMQ connection cleanup and add a focused regression test without requiring a broker.
- Establish a focused, reproducible flake8 gate for syntax errors, undefined names and other selected correctness checks; keep the full lint report available without requiring an immediate cleanup of all existing findings.
- Declare the dynamically injected plugin loggers explicitly while preserving loader injection and keeping undefined-name checks enabled.
- Narrow the JSON logger's bare exception handler and test both ordinary formatting errors and control-flow exceptions.
- Run the focused lint gate in CI without removing the existing Python test matrix; document the selected rules and full-report command.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `developer-experience`: contributors and CI receive a repeatable, correctness-focused lint check.
- `builtin-plugin-test-coverage`: the RabbitMQ exclusion is narrowed to permit a focused connection-cleanup regression test, without requiring transport simulation or general RabbitMQ coverage.

## Impact

- `notificationforwarder/src/notificationforwarder/`: RabbitMQ cleanup, four dynamically injected logger bindings and JSON traceback exception handling.
- `notificationforwarder/tests/`: targeted cleanup and exception-handling tests; the full suite remains required.
- `notificationforwarder/.flake8`, documentation and the notificationforwarder GitHub Actions workflow: reproducible lint configuration and CI gate.
- Existing unselected lint findings remain visible in an explicit full-report run; no broad formatting sweep or eventhandler cleanup is planned.
