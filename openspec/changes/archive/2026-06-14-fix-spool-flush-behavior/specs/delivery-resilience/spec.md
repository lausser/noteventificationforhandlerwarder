## MODIFIED Requirements

### Requirement: Failed deliveries are either persisted or explicitly surfaced
The system SHALL ensure that a failed delivery attempt results in one of two observable outcomes: the event is durably spooled for retry within the configured retention window, or the runtime emits an explicit error describing why spooling could not be completed.

#### Scenario: Submission fails and event is spooled
- **WHEN** a forwarder submit operation returns failure for a formatted event
- **THEN** the runtime stores the event in the spool and logs that the event will be retried

### Requirement: Retry behavior is bounded by retention policy
The system SHALL retry previously spooled events only while they remain inside the configured spool retention window, and SHALL stop retrying expired events in a visible and deterministic way.

#### Scenario: Expired spooled event is encountered during flush
- **WHEN** the runtime processes a spooled event that is older than the configured retention window
- **THEN** the runtime removes or skips that event according to the documented policy and logs that the event expired

### Requirement: Flush execution avoids unsafe concurrent replay
The system SHALL protect flush operations against unsafe concurrent execution for the same forwarder instance so that the same spooled event is not replayed multiple times by overlapping flush attempts.

#### Scenario: Concurrent flush attempt is detected
- **WHEN** a second flush attempt starts while another flush for the same forwarder is already in progress
- **THEN** the runtime prevents overlapping replay for that forwarder instance and records that the concurrent flush was suppressed or deferred

### Requirement: Recovery attempts are observable
The system SHALL log enough structured information about spool counts, retry attempts, retry outcomes, and final delivery outcomes so that operators can understand whether the system is recovering from downstream failures.

#### Scenario: Spool replay succeeds after prior failures
- **WHEN** previously spooled events are flushed successfully
- **THEN** the runtime logs how many events were retried and that delivery recovery succeeded

## ADDED Requirements

### Requirement: Discarded events are not replayed during flush
The system SHALL NOT re-submit events that are marked as discarded during spool replay. Discarded events encountered during flush SHALL be deleted from the spool and logged as trash.

#### Scenario: Discarded event encountered during flush
- **WHEN** a spooled event is reformatted during flush and the resulting formatted event has `is_discarded=True`
- **THEN** the runtime deletes the event from the spool without submitting it and logs that the discarded event was skipped

### Requirement: Summary logging is restored after flush
The system SHALL reset the baseclass summary logging flag at the start of each flush cycle so that the summary log is available for subsequent forward operations.

#### Scenario: Summary logging resumes after flush
- **WHEN** a flush cycle completes and a subsequent forward operation succeeds
- **THEN** the runtime logs the baseclass summary message for that forward operation
