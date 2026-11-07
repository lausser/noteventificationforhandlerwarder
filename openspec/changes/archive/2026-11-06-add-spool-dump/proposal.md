# Proposal

## Why

When a downstream receiver is unreachable, notificationforwarder spools failed events in a per-forwarder SQLite database and the operator can only learn the queue length from log lines. There is no way to inspect which events are stuck, when they were spooled, or their content without hand-crafting `sqlite3` queries against a file whose name depends on the forwarder and its tag. Operators need a first-class way to dump the spool contents of a forwarder instance.

## What Changes

- Extend the existing `notificationforwarder` CLI with a `--dump-spool` mode (no new script). The same commandline parameters as a normal notification command are accepted; `--forwarder` (required in dump mode — the `syslog` default does not apply) and `--forwardertag` select the spool database, and every outcome, including an empty spool, names the resolved database path and table.
- Two new modifier parameters:
  - `--order oldest|newest` (default `oldest`) — sort by the database `timestamp` column (the original spool time, stable across `move_to_end` re-inserts), tie-broken by `id` (ascending for oldest, descending for newest).
  - `--limit N` (no default) — limit the number of records displayed; when omitted, all records are shown.
- Dump output is complete and systematic per record: record number (`id`, the same identifier the spool log lines use as `event_id`), spool time (database `timestamp`), and the full event details (decoded JSON payload, verbatim).
- `--dump-format text|json` (default `text`) — `json` emits a machine-readable array on stdout so the output can be piped to `jq`; human-facing header/summary lines go to stderr so stdout stays clean in both modes.
- Corrupt/undecodable payloads do not abort the dump: the record is shown with a marker and the raw text prefix.
- The dump is a read-only path: it does not load the forwarder module, does not run formatters/reporters, does not probe, does not flush, does not acquire the flush lock, and does not take the `--eventopt` values through the normal forward pipeline.
- Non-goals (explicitly out of scope): no modification of the spool database schema or stored columns (the failure reason is logged, not stored — operators correlate the spool log via `event_id`); no new failure-reason persistence; nothing for eventhandler (it has no spool database).

## Capabilities

### New Capabilities

- `spool-inspection`: operator-facing read-only inspection of the spool database — a dump mode on the existing CLI with ordering and limiting, a defined output format and stream discipline, and defined behavior for empty, missing, and corrupt spool databases.

### Modified Capabilities

None. The existing `thread-safe-spool-store` and `delivery-resilience` contracts (write path, retry, pruning, locks) are unchanged by this change.

## Impact

- `notificationforwarder/bin/notificationforwarder` — new `--dump-spool`, `--order`, `--limit`, `--dump-format` parameters and the dump branch.
- `notificationforwarder/src/notificationforwarder/` — a small read-only dump module (DB path derivation from `RuntimeConfig`, ordered/limited SELECT, record formatting); no changes to `spool.py` write semantics or `baseclass.py` forwarding flow.
- Tests — a dump test layer exercising ordering, limit, both formats, corrupt payloads, and empty/missing DB behavior, following the existing test conventions.
- No dependency changes; `sqlite3` and `argparse` are already in use.
