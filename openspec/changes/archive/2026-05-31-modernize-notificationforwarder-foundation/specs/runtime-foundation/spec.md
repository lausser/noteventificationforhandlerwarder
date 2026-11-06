## ADDED Requirements

### Requirement: Runtime orchestration has explicit responsibilities
The system SHALL separate runtime orchestration responsibilities so that component loading, environment/path initialization, event formatting, delivery execution, reporting, and logging coordination are implemented as explicit runtime concerns rather than as hidden side effects spread across the forwarding flow.

#### Scenario: Forwarding an event uses a defined runtime flow
- **WHEN** a caller creates a forwarder instance and submits an event for processing
- **THEN** the runtime executes a defined sequence that initializes runtime state, resolves the formatter, formats the event, attempts delivery, and records the outcome through the configured logger

### Requirement: Component loading failures are actionable
The system SHALL provide actionable failures when forwarders, formatters, reporters, or loggers cannot be loaded, including enough context to identify which component failed and which resolution rule was attempted.

#### Scenario: Formatter module cannot be loaded
- **WHEN** the runtime is asked to use a formatter that cannot be imported or instantiated
- **THEN** the runtime reports a component-loading failure that identifies the formatter name and does not continue as if formatting had succeeded

### Requirement: Logger selection is deterministic
The system SHALL resolve the configured logger type deterministically and SHALL use a documented fallback behavior when the requested logger implementation is unavailable.

#### Scenario: Requested logger implementation is invalid
- **WHEN** a caller requests a logger type that cannot be loaded
- **THEN** the runtime falls back to the default text logger and emits a warning that explains the fallback

### Requirement: Runtime path initialization is consistent
The system SHALL derive runtime files such as log files, temporary files, and spool database paths from a consistent environment and naming strategy so that all runtime artifacts for a forwarder instance are predictable.

#### Scenario: Runtime initializes site-local paths
- **WHEN** a forwarder instance is created for a named target in an OMD environment
- **THEN** the runtime assigns predictable log, lock, and spool paths derived from the configured site root and forwarder identity
