## ADDED Requirements

### Requirement: Nostr websocket startup is quiet
The `notificationforwarder` system SHALL avoid emitting the known `websocket_ping_timeout` warning during normal Nostr forwarder initialization.

#### Scenario: Default Nostr startup does not warn
- **WHEN** the Nostr forwarder starts with its standard websocket configuration
- **THEN** the runtime MUST not print the `websocket_ping_timeout` warning to the console or logs
- **AND** Nostr publishing MUST continue to work normally

#### Scenario: Warning suppression does not change delivery behavior
- **WHEN** the forwarder initializes a relay connection after applying the quiet startup behavior
- **THEN** the relay connection MUST still be usable for publishing notifications
- **AND** the system MUST preserve the existing fail-fast behavior for missing `pynostr`
