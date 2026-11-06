## Why

The notificationforwarder documentation has gaps that prevent users from understanding and using two important features:

1. **Heartbeat events** are not documented at all. The `is_heartbeat` flag exists in the FormattedEvent class and affects spooling behavior (heartbeat events skip the spool on failure), but neither README.md nor INDEX.md explain this concept or how to use it.
2. **The spool flush mechanism and probe() method** are not documented. Every event triggers the flush phase in `forward_formatted()` — checking for spooled events, optionally calling `probe()` to verify the receiver is reachable, and flushing if possible. The `probe()` method on forwarders is mentioned briefly in the webhook example but never explained as a concept. Users don't understand when flush happens, what probe() does, or why heartbeats solve the "quiet period" problem (no real notifications → no flush attempts → spooled events sit for hours).
3. **The Nostr forwarder/formatter** is documented in README.md but missing from INDEX.md (the omd.consol.de user documentation site), so users visiting the public docs have no visibility into this feature.

## What Changes

- Add documentation for the spool flush mechanism: how every event triggers the flush phase, how probe() gates flush attempts, and the three probe scenarios (has probe + True, has probe + False, no probe).
- Add documentation for heartbeat events: what they are, that they skip spooling on failure, and that their unique value is providing a guaranteed regular flush trigger even when nothing breaks in the monitored infrastructure.
- Add a Nagios/Naemon service example showing how to schedule periodic heartbeats as a check_command (service always OK, used purely as a scheduler).
- Copy the Nostr documentation section from README.md to INDEX.md so the omd.consol.de site has complete plugin coverage.

## Capabilities

### New Capabilities

- `heartbeat-and-probe-documentation`: Documentation covering the spool flush mechanism (general), probe() method (general), heartbeat event semantics (is_heartbeat flag, spool-bypass), and a practical guide for scheduling heartbeat services in Nagios/Naemon as a periodic flush trigger.

### Modified Capabilities

- `nostr-notificationforwarder`: The Nostr documentation already exists in README.md; INDEX.md needs to include the same content for the public omd.consol.de documentation site.

## Impact

- Files modified: `notificationforwarder/README.md`, `notificationforwarder/INDEX.md`
- No code changes, no dependency changes
- Pure documentation update
