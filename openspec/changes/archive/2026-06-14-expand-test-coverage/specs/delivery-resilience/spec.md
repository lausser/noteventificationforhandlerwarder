## ADDED Requirements

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
The system SHALL remove spooled events that are discarded during replay (logging "delete trash event"), keep persistently failing events and log "event stays in spool" with loop termination when the count is unchanged, treat spool init failure as unrecoverable with a critical log, and correctly compute attempted/recovered/stayed/deleted_trash counts when flush processes more than the batch limit.

#### Scenario: spool-replay-discarded-event-deleted
- **WHEN** a spooled raw event is re-formatted during flush and the formatter calls discard()
- **THEN** the entry is removed as trash and "delete trash event" is logged

#### Scenario: spool-replay-persistent-failure-stays
- **WHEN** replayed submit keeps failing
- **THEN** "event stays in spool" is logged and the flush loop terminates when the count of remaining events is unchanged

#### Scenario: spool-init-failure-unrecoverable
- **WHEN** database initialization is broken
- **THEN** spool() returns False and a critical "delivery failed and event could not be persisted" is logged

#### Scenario: spool-flush-beyond-batch-limit
- **WHEN** more than 10 events are spooled and flush runs with fetch_batch(limit=10)
- **THEN** the stuck-detection logic (last_events_to_flush == events_to_flush) triggers correctly and the final "spool replay summary" reports accurate attempted/recovered/stayed/deleted_trash counts
