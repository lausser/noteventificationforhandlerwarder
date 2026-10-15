## ADDED Requirements

### Requirement: Every flush logs the remaining spool queue length
At the end of every flush that acquired the flush lock, the system SHALL log "spooling queue length" at info level with `queue_length` set to the number of events in the spool at that moment, including events spooled by other processes during the flush. The message and field SHALL be the same as in the line logged when an event is spooled.

#### Scenario: queue-length-zero-after-drain
- **WHEN** a flush delivers every spooled event
- **THEN** it logs "spooling queue length" with `queue_length` 0 at info level

#### Scenario: queue-length-after-stopped-flush
- **WHEN** a flush stops at a failed replay with three events in the spool
- **THEN** it logs "spooling queue length" with `queue_length` 3

#### Scenario: queue-length-includes-concurrently-spooled-events
- **WHEN** another process spools an event while a flush delivers all events of its snapshot
- **THEN** the flush logs `queue_length` 1

#### Scenario: queue-length-not-logged-without-lock
- **WHEN** a flush does not get the flush lock
- **THEN** it does not log "spooling queue length"

#### Scenario: queue-length-json-format
- **WHEN** the JSON logger is used and a flush drains the spool
- **THEN** the log line matches `"message":"spooling queue length","queue_length":(\d+)` with the value 0
