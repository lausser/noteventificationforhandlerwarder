## Purpose

Guarantee that delivery failures are durably persisted or explicitly surfaced, retries are bounded, concurrent flush is safe, and recovery is observable — so operators can trust the system handles downstream outages correctly.

## Requirements

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

### Requirement: Resilience tests live in a clearly named layer and cover both shipped and own-module paths uniformly
The system SHALL place all resilience/spool/heartbeat/probe/enrichment/formatter-failure/spool-replay tests in a dedicated flat layer file (test_resilience_spool.py on notificationforwarder, test_resilience_concurrency.py on eventhandler) that exercises the same behaviors whether the formatter/forwarder/decider/runner under test is a shipped module or a user-written module loaded from the pythonpath fixtures.

#### Scenario: A new resilience edge (e.g. probe-gated flush or heartbeat no-spool) is added
- **WHEN** a resilience test for a shipped forwarder and the equivalent behavior through an own-module forwarder loaded via the pythonpath tree are both present in the resilience layer file
- **THEN** both the shipped and own-module paths are shown to obey the same observable contract (return values, spool rows or their absence, log messages, stuck-detection counts, etc.).

### Requirement: Heartbeat events never create spool entries on failure; non-heartbeat failures do spool
The system SHALL ensure that when a forwarder submit_one fails inside forward() for a heartbeat event, no spool row is written, while the same failure for a non-heartbeat event results in a durable spool entry.

#### Scenario: webhook-heartbeat-failure-no-spool
- **WHEN** a webhook submit_one fails with is_heartbeat=True via forward()
- **THEN** zero events are spooled (contrast with non-heartbeat behavior)

#### Scenario: webhook-non-heartbeat-failure-spools
- **WHEN** the same failure path is taken without is_heartbeat
- **THEN** the event is spooled

### Requirement: Probe-gated flush prevents unsafe replay when the forwarder cannot currently succeed
The system SHALL skip calling flush() when a forwarder that implements probe() returns False and the spool is non-empty; when probe() returns True, or when the forwarder has no probe() method, flush proceeds for a non-empty spool.

#### Scenario: flush-skipped-when-probe-fails
- **WHEN** a forwarder with a probe() method returns False and the spool has entries
- **THEN** forward_formatted() does not invoke flush()

#### Scenario: flush-runs-when-probe-succeeds
- **WHEN** probe() returns True and the spool has entries
- **THEN** the spooled events are replayed before any new event is submitted

#### Scenario: flush-runs-without-probe-method
- **WHEN** a forwarder (e.g. webhook) has no probe() method and the spool is non-empty
- **THEN** flush is attempted

### Requirement: Enrichment strips unexpanded macros while preserving nested structures and adding OMD metadata
The system SHALL remove any value that is exactly an unexpanded $<WORD>$ token from the raw event before formatting, leave dict/list values untouched by the stringification pass, and inject the four omd_* metadata fields.

#### Scenario: enrich-strips-unexpanded-macros
- **WHEN** a raw event contains HOSTNAME='$HOSTNAME$' and FOO='$'
- **THEN** those macro tokens are removed before the event reaches any formatter

#### Scenario: enrich-preserves-nested-structures
- **WHEN** eventopt values contain nested dicts or lists
- **THEN** the structures are not corrupted by any stringification performed during enrichment

#### Scenario: enrich-adds-omd-metadata
- **WHEN** any raw event is enriched
- **THEN** omd_site, omd_originating_host, omd_originating_fqdn, and omd_originating_timestamp are present on the event

### Requirement: Formatting failures abort delivery without spooling the raw event
The system SHALL treat an incomplete formatted event (payload present but summary missing, or vice versa) and any exception raised by the formatter as fatal for that event: a critical log is emitted and no delivery attempt or spooling occurs.

#### Scenario: incomplete-formatted-event-aborts
- **WHEN** a formatter sets payload but not summary (or vice versa)
- **THEN** a critical log "formatted event incomplete" is emitted and no delivery is attempted

#### Scenario: formatter-exception-no-spool
- **WHEN** a formatter raises an exception
- **THEN** a critical log is emitted and the raw event is not spooled

#### Scenario: missing-formatter-module-aborts
- **WHEN** an unknown formatter name is requested
- **THEN** a critical log "found no formatter module" is emitted and processing aborts gracefully

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

### Requirement: Pruning expired events does not block concurrent spooling
Removing expired events at the start of a flush SHALL be committed immediately, so that other processes can spool events while the flush is replaying, even if every replay attempt fails.

#### Scenario: spool-while-flush-replays-after-prune
- **WHEN** a flush has removed expired events and is still replaying, and another process spools an event
- **THEN** the event is stored without a "database is locked" error

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
