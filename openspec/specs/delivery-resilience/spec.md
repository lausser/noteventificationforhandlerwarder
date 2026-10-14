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
