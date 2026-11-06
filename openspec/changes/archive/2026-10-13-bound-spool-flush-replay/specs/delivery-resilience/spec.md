## MODIFIED Requirements

### Requirement: Spool replay correctly handles discard-during-replay, persistent failures, init failures, and batch-limit loops
The system SHALL remove spooled events that are discarded during replay (logging "delete trash event"), keep persistently failing events and log "event stays in spool" with loop termination when a replay batch makes no progress, treat spool init failure as unrecoverable with a critical log, and correctly compute attempted/recovered/stayed/deleted_trash counts when flush processes more than the batch limit.

#### Scenario: spool-replay-discarded-event-deleted
- **WHEN** a spooled raw event is re-formatted during flush and the formatter calls discard()
- **THEN** the entry is removed as trash and "delete trash event" is logged

#### Scenario: spool-replay-persistent-failure-stays
- **WHEN** replayed submit keeps failing
- **THEN** "event stays in spool" is logged, the event remains in the spool, and the flush loop terminates after the first batch in which no event was replayed or removed

#### Scenario: spool-init-failure-unrecoverable
- **WHEN** database initialization is broken
- **THEN** spool() returns False and a critical "delivery failed and event could not be persisted" is logged

#### Scenario: spool-flush-beyond-batch-limit
- **WHEN** more than 10 events are spooled and flush runs with fetch_batch(limit=10)
- **THEN** a batch without progress ends the flush with the critical "spooled events could not be submitted" log and the final "spool replay summary" reports accurate attempted/recovered/stayed/deleted_trash counts

## ADDED Requirements

### Requirement: Flush replay is bounded to the events spooled before it started
A flush SHALL replay only events that were in the spool when the flush started, and SHALL attempt each of them at most once. Events spooled by concurrent processes while a flush runs SHALL stay in the spool for a later flush. The time a flush holds the flush lock SHALL therefore not depend on how many events arrive while it runs.

#### Scenario: flush-terminates-while-other-processes-spool
- **WHEN** every replayed submit fails and another process spools a new event after each failed submit
- **THEN** the flush terminates after the first batch without progress, each originally spooled event was submitted at most once, and both the original and the concurrently spooled events remain in the spool

#### Scenario: stuck-log-counts-only-snapshot-events
- **WHEN** a flush stops because a batch made no progress while other processes have spooled further events
- **THEN** the critical "spooled events could not be submitted" log reports in `spooled_count` only the events from the flush's start that are still spooled

#### Scenario: flush-skips-events-spooled-during-flush
- **WHEN** an event is spooled by another process while a flush is running
- **THEN** that flush does not replay it and the event is replayed by a later flush

### Requirement: Pruning expired events does not block concurrent spooling
Removing expired events at the start of a flush SHALL be committed immediately, so that other processes can spool events while the flush is replaying, even if every replay attempt fails.

#### Scenario: spool-while-flush-replays-after-prune
- **WHEN** a flush has removed expired events and is still replaying, and another process spools an event
- **THEN** the event is stored without a "database is locked" error
