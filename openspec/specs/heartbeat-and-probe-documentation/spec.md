## Purpose

Document the spool flush mechanism, probe method, heartbeat events, and related operational patterns in the notificationforwarder framework.

## Requirements

### Requirement: Spool flush mechanism documentation
The documentation SHALL explain that every event triggers the flush phase in `forward_formatted()` before its own submission, and that this mechanism attempts to re-submit previously spooled events.

#### Scenario: User learns about flush as a general mechanism
- **WHEN** a user reads the flush documentation
- **THEN** the documentation SHALL state that flush happens for every event, not just heartbeats
- **AND** the documentation SHALL explain that flush checks for spooled events and attempts to re-submit them

### Requirement: Probe method documentation
The documentation SHALL explain that forwarders can implement an optional `probe()` method which returns True if the receiving system is reachable, and that probe() is called before flushing spooled events as an optimization.

#### Scenario: User reads about probe() with receiver available
- **WHEN** a user reads the probe() section and the forwarder has a probe() method that returns True
- **THEN** the documentation SHALL explain that flush proceeds because the receiver is known to be up

#### Scenario: User reads about probe() with receiver unavailable
- **WHEN** a user reads the probe() section and the forwarder has a probe() method that returns False
- **THEN** the documentation SHALL explain that flush is skipped to avoid wasted submit() calls

#### Scenario: User reads about forwarder without probe()
- **WHEN** a user reads the probe() section and the forwarder has no probe() method
- **THEN** the documentation SHALL explain that flush proceeds anyway because there is no way to pre-check

### Requirement: Heartbeat event documentation
The documentation SHALL explain that formatters can set `event.is_heartbeat = True` on a FormattedEvent to mark it as a heartbeat event, that heartbeat events are NOT spooled when delivery fails, and that their unique value is providing a guaranteed regular flush trigger.

#### Scenario: User learns about heartbeat spool bypass
- **WHEN** a user reads the heartbeat events section
- **THEN** the documentation SHALL state that heartbeat events skip the spool database on forwarder failure
- **AND** the documentation SHALL explain this prevents periodic check-in events from accumulating in the retry queue

#### Scenario: User learns about heartbeat flush frequency
- **WHEN** a user reads the heartbeat events section
- **THEN** the documentation SHALL explain that while every event triggers flush, heartbeats guarantee regular flush attempts even in healthy systems where no real notifications are being sent
- **AND** the documentation SHALL contrast this with the "quiet period" problem where spooled events sit for hours without flush attempts

### Requirement: Nagios heartbeat service example
The documentation SHALL include a concrete example of how to define a Nagios/Naemon service that periodically sends heartbeat events to notificationforwarder, using the service as a scheduler rather than a health check.

#### Scenario: User configures a heartbeat service
- **WHEN** a user reads the Nagios heartbeat example
- **THEN** the documentation SHALL provide a command definition using NOTIFICATIONTYPE=HEARTBEAT
- **AND** the documentation SHALL provide a service definition with check_interval for periodic scheduling
- **AND** the documentation SHALL explain that the service always exits OK (notificationforwarder exits 0) and is used purely as a scheduling mechanism
- **AND** the documentation SHALL show notification_options n and notification_interval 0 to suppress Nagios-level notifications
