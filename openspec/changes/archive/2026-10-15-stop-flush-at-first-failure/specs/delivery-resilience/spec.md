## MODIFIED Requirements

### Requirement: Spool replay correctly handles discard-during-replay, persistent failures, init failures, and batch-limit loops
The system SHALL remove spooled events that are discarded during replay (logging "delete trash event"), keep persistently failing events and log "event stays in spool" with loop termination at the first failed replay, treat spool init failure as unrecoverable with a critical log, and correctly compute attempted/recovered/stayed/deleted_trash counts when flush processes more than the batch limit.

#### Scenario: spool-replay-discarded-event-deleted
- **WHEN** a spooled raw event is re-formatted during flush and the formatter calls discard()
- **THEN** the entry is removed as trash and "delete trash event" is logged

#### Scenario: spool-replay-persistent-failure-stays
- **WHEN** replayed submit keeps failing
- **THEN** "event stays in spool" is logged, the event remains in the spool, and the flush loop terminates after the first failed replay

#### Scenario: spool-init-failure-unrecoverable
- **WHEN** database initialization is broken
- **THEN** spool() returns False and a critical "delivery failed and event could not be persisted" is logged

#### Scenario: spool-flush-beyond-batch-limit
- **WHEN** more than 10 events are spooled, flush runs with fetch_batch(limit=10), and the first 11 replays succeed while the 12th fails
- **THEN** the flush continues into the second batch, stops at the 12th event with the critical "spooled events could not be submitted" log, and the final "spool replay summary" reports attempted=12, recovered=11, stayed_in_spool=1

### Requirement: Flush replay is bounded to the events spooled before it started
A flush SHALL replay only events that were in the spool when the flush started, and SHALL attempt each of them at most once. Events spooled by concurrent processes while a flush runs SHALL stay in the spool for a later flush. The time a flush holds the flush lock SHALL therefore not depend on how many events arrive while it runs.

#### Scenario: flush-terminates-while-other-processes-spool
- **WHEN** every replayed submit fails and another process spools a new event after each failed submit
- **THEN** the flush terminates after the first failed submit, only the first originally spooled event was submitted, and both the original and the concurrently spooled events remain in the spool

#### Scenario: stuck-log-counts-only-snapshot-events
- **WHEN** a flush stops at a failed replay while other processes have spooled further events
- **THEN** the critical "spooled events could not be submitted" log reports in `spooled_count` only the events from the flush's start that are still spooled

#### Scenario: flush-skips-events-spooled-during-flush
- **WHEN** an event is spooled by another process while a flush is running
- **THEN** that flush does not replay it and the event is replayed by a later flush

## ADDED Requirements

### Requirement: Flush stops at the first failed replay
A flush SHALL stop at the first spooled event whose replay fails, either because submit reports failure or because it raises an exception (including a submit timeout). Later spooled events SHALL NOT be submitted by that flush. Events removed during replay because they are discarded or cannot be formatted SHALL NOT stop the flush.

#### Scenario: flush-stops-at-first-failed-replay
- **WHEN** three events are spooled and the replay of the first one fails
- **THEN** the second and third events are not submitted, all three stay in the spool, and the flush has called submit exactly once

#### Scenario: flush-stops-after-successful-replays
- **WHEN** three events are spooled, the first replay succeeds, and the second one fails
- **THEN** the first event is removed, the third is not submitted, and the second and third stay in the spool

#### Scenario: flush-stops-on-submit-timeout
- **WHEN** the replay of the first spooled event runs into the submit timeout
- **THEN** the flush stops without submitting the following events

#### Scenario: flush-continues-after-trash
- **WHEN** the first spooled event is discarded by the formatter during replay and the second one is replayed successfully
- **THEN** both are removed from the spool

### Requirement: An event rejected while the receiver accepts others moves to the end of the spool
If a flush stopped at a failed event and the same process then submits a live event successfully, the system SHALL move the stopped event behind all other spooled events, keeping its payload and original spool timestamp, and SHALL log this at critical level. The move SHALL happen only while holding the flush lock.

#### Scenario: rejected-event-moves-to-end
- **WHEN** events 1, 2 and 3 are spooled, the replay of event 1 fails, and the live event is then submitted successfully
- **THEN** the spool contains events 2, 3, 1 in this replay order, event 1 has its original spool timestamp, and a critical log names event 1 as moved to the end of the spool

#### Scenario: no-move-when-live-submit-fails
- **WHEN** a flush stopped at a failed event and the live event's submit fails too
- **THEN** the stopped event keeps its position and the live event is spooled behind it

#### Scenario: no-move-without-live-submit
- **WHEN** a flush stopped at a failed event and no live event is submitted afterwards
- **THEN** the stopped event keeps its position

#### Scenario: heartbeat-success-moves-rejected-event
- **WHEN** a flush stopped at a failed event and the live event is a heartbeat that is submitted successfully
- **THEN** the stopped event is moved to the end of the spool

#### Scenario: no-move-while-another-process-flushes
- **WHEN** the move would happen but another process holds the flush lock
- **THEN** the event keeps its position, nothing is logged at critical level for the move, and a later flush that stops at the same event moves it

#### Scenario: no-move-when-event-is-gone
- **WHEN** the stopped event has been delivered and removed by another process before the move
- **THEN** no event is moved or duplicated

#### Scenario: no-move-when-event-is-already-last
- **WHEN** the stopped event is the last event in the spool
- **THEN** it is not moved and nothing is logged for a move

#### Scenario: moved-event-still-expires
- **WHEN** an event that was moved to the end of the spool becomes older than `max_spool_minutes`, measured from its original spool time
- **THEN** the next flush drops it as an outdated event
