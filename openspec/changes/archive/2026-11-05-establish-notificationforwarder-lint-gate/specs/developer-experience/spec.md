# Spec Delta

## ADDED Requirements

### Requirement: Notificationforwarder has a correctness-focused lint gate
The project SHALL provide a documented, reproducible lint check of notificationforwarder source code that fails for undefined names, syntax errors, other selected structural errors and bare exception handlers. The notificationforwarder CI workflow SHALL run that check and fail when it fails.

#### Scenario: An undefined name is introduced
- **WHEN** a contributor introduces an undefined name into notificationforwarder source
- **THEN** the focused lint check and CI fail with an actionable diagnostic

#### Scenario: A dynamically injected logger is used
- **WHEN** a built-in forwarder is loaded by the component loader and uses its injected logger
- **THEN** the focused lint check accepts that valid usage without disabling undefined-name detection globally

#### Scenario: A contributor runs the complete report
- **WHEN** a contributor follows the documented full-report command
- **THEN** findings outside the focused gate are reported without being represented as fixed or necessarily harmless

#### Scenario: Existing test matrix remains available
- **WHEN** the lint gate is added to CI
- **THEN** the existing notificationforwarder Python test matrix continues to run

### Requirement: JSON traceback formatting preserves control-flow exceptions
The JSON logger SHALL tolerate ordinary exceptions while formatting exception traces without swallowing control-flow exceptions.

#### Scenario: Trace formatting encounters an ordinary exception
- **WHEN** trace formatting raises an ordinary exception
- **THEN** logging continues without the formatted trace

#### Scenario: Trace formatting is interrupted
- **WHEN** trace formatting raises KeyboardInterrupt or SystemExit
- **THEN** the control-flow exception propagates
