## MODIFIED Requirements

### Requirement: Failed executions are either surfaced or recoverable through forwarding
The system SHALL ensure that a failed runner execution or downstream forwarder handoff results in one of two observable outcomes: the failure is explicitly surfaced with enough context to diagnose the issue, or the runtime persists the result for retry within the configured recovery mechanism.

#### Scenario: Runner execution fails
- **WHEN** a runner operation fails for a decided event
- **THEN** the runtime emits a failure that identifies the command or action that failed and preserves the event context for recovery or operator review

### Requirement: Retry behavior is bounded by retention policy
The system SHALL retry recoverable results only while they remain inside the configured retention window, and SHALL stop retrying expired results in a visible and deterministic way.

#### Scenario: Expired recoverable result is encountered
- **WHEN** the runtime processes a recoverable result that is older than the configured retention window
- **THEN** the runtime removes or skips that result according to the documented policy and logs that the result expired

### Requirement: Replay execution avoids unsafe concurrent duplication
The system SHALL protect replay or recovery operations against unsafe concurrent execution for the same handler instance so that the same event is not processed multiple times by overlapping recovery attempts.

#### Scenario: Concurrent recovery attempt is detected
- **WHEN** a second recovery attempt starts while another recovery attempt for the same handler is already in progress
- **THEN** the runtime prevents overlapping replay for that handler instance and records that the concurrent attempt was suppressed or deferred

### Requirement: Recovery attempts are observable
The system SHALL log enough structured information about execution outcomes, retry attempts, retry outcomes, and final delivery outcomes so that operators can understand whether the system is recovering from downstream failures.

#### Scenario: A forwarded result succeeds after prior failures
- **WHEN** a previously failed event or notification is recovered successfully
- **THEN** the runtime logs how many attempts were made and that recovery succeeded
