## Context

The notificationforwarder has two documentation files:
- `README.md` — shown on GitHub, contains both user and developer documentation
- `INDEX.md` — shown on omd.consol.de, targets end users only

Both files are missing documentation for the spool flush mechanism, heartbeat events, and the probe() method. INDEX.md is also missing the Nostr section that exists in README.md.

The flush mechanism is a general feature: every event that goes through `forward_formatted()` triggers a flush phase before its own submission. The `probe()` method is a general optimization: it pre-checks whether the receiver is reachable before attempting flush, avoiding wasted submit() calls when the receiver is known to be down. The heartbeat feature (`FormattedEvent.is_heartbeat` flag set by formatters) has two effects: (1) heartbeat events skip the spool database on failure, and (2) they provide a guaranteed regular flush trigger even in healthy systems where no real notifications are being sent.

## Goals / Non-Goals

**Goals:**
- Document the spool flush mechanism as a general feature (happens for every event in `forward_formatted()`)
- Document the probe() method: when to implement it, how it gates flush attempts, the three scenarios
- Document heartbeat events: what they are, how to set them, that they skip spooling, and that their unique value is guaranteed flush frequency in healthy systems
- Provide a practical guide for using heartbeat events with Nagios/Naemon (scheduling as a check_command, service definition)
- Sync the Nostr section from README.md into INDEX.md

**Non-Goals:**
- Document the internal runtime architecture (runtime_config.py, component_loader.py, etc.) — that is developer-facing and belongs in README.md only
- Change any code behavior
- Restructure the overall documentation layout

## Decisions

**Decision: Present flush mechanism first, then probe(), then heartbeat**

Rationale: The flush mechanism is the general concept (every event triggers it). Probe() is the optimization that gates it. Heartbeat is the specific use case that solves the "quiet period" problem. This ordering builds understanding progressively: general → optimization → application.

**Decision: Clarify that flush is NOT heartbeat-specific**

Rationale: A common misconception is that heartbeats "trigger" flush in a special way. In reality, every event triggers flush. The heartbeat's unique contribution is guaranteed frequency — even when nothing breaks, heartbeats ensure flush attempts happen regularly so spooled events don't sit for hours.

**Decision: Include a practical Nagios service example for heartbeat scheduling**

Rationale: Users need to know how to actually schedule periodic heartbeats. The service uses notificationforwarder as check_command (always exits OK), effectively using Nagios as a scheduler. The service definition should show `notification_options n` and `notification_interval 0` to suppress Nagios-level notifications.

**Decision: Keep the Runtime Architecture section in README.md only**

Rationale: As discussed, this is developer-facing content about internal code organization. It doesn't help users configure or use notificationforwarder.

## Risks / Trade-offs

- [Risk] Documentation drift between README.md and INDEX.md over time → Mitigation: The heartbeat/probe and Nostr sections will be identical; a comment or note could flag that INDEX.md is the user-facing subset
- [Risk] Heartbeat section might confuse users who don't need it → Mitigation: Place it after the core concepts (formatter/forwarder/reporter) and before the built-in plugins, so it's optional reading
