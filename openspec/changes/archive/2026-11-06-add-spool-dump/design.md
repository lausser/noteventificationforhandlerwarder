# Design

See proposal.md for the motivation and the spool-inspection spec for the behavior contract. This covers how.

## Context

The spool is a per-forwarder-instance SQLite database. Its location and table name are already a pure function of `(forwarder, tag)` plus the environment:

- `RuntimeConfig.build_paths()` → `db_file = $OMD_ROOT/var/tmp/notificationforwarder_<forwarder_name>_notifications.db`
- `NotificationForwarder.init_db()` → `table_name = "events_" + forwarder_name`
- `forwarder_name = forwarder + ("_" + tag if tag)` (see `RuntimeConfig.forwarder_name`)

The table schema (created by `SpoolStore.init_db()`) is exactly:
```
id        INTEGER PRIMARY KEY
payload   TEXT NOT NULL            -- json.dumps(raw_event)
timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
```
`timestamp` is a `YYYY-MM-DD HH:MM:SS` UTC string (fixed-width, so lexicographic order == chronological order). `move_to_end()` re-inserts a row copying `payload` **and** `timestamp`, so the stored timestamp is the original spool time and is stable across failed replays.

The dump needs only `forwarder`, `tag`, and `OMD_ROOT` to locate the table. The full forwarder/formatter/reporter pipeline is irrelevant to a read.

## Goals / Non-Goals

Goals:
- A `--dump-spool` branch on the existing CLI that reads the right table, orders by `timestamp` (tie-break `id`), applies an optional limit, and prints records.
- A dedicated, unit-testable read path in a small module, called by the CLI.
- Stream discipline: record data on stdout, informational lines on stderr, in both text and JSON output.
- Strict read-only: the spool is never modified, the flush lock is never taken, and no plugin module is loaded.

Non-Goals:
- No schema change, no new stored column, no failure-reason derivation (out of scope by decision; the reason stays in the spool log, correlated by record number).
- No changes to `spool.py` write semantics, `baseclass.py` forwarding flow, retry, pruning, or locking.
- Nothing for eventhandler (it has no spool database).

## Decisions

### 1. Lightweight read-only path — do not call `baseclass.new()`, and require an explicit forwarder
The dump computes the DB path itself from `forwarder`/`tag`/`OMD_ROOT` (the same logic `RuntimeConfig.build_paths()` already expresses) and opens the table directly. In dump mode the forwarder argument is required: the CLI's `syslog` default is not applied, and omitting it is a usage error (non-zero exit, message on stderr, no record data on stdout). The tag remains optional and selects the untagged instance.

- **Why**: a dump is an operational triage action, typically reached *while delivery is failing*. Forcing a full forwarder/formatter/reporter load to read a file couples the dump to plugin dependencies that may be exactly what is broken. The path is a pure function, so nothing is lost.
- **Why require the forwarder**: the spool file is a pure function of `(forwarder, tag)`. If the operator pastes a Naemon command and forgets `--forwarder webhook --forwardertag prod`, the `syslog` default silently dumps the (likely drained) syslog spool and — with an empty-spool-is-healthy contract — reports "spool empty", exit 0. The operator stops investigating, and `max_spool_minutes` (default 5) prunes the real rows. Naming the instance is cheap and removes the worst failure mode. The Naemon command the operator copies already carries the forwarder, so nothing is lost.
- **Alternative considered**: instantiate the forwarder via `baseclass.new()` and read its `spool_store`. Rejected — it loads modules, sets up logging and the reporter, and runs `init_db()` (a write transaction that creates the table), which violates the read-only goal and adds cost and failure modes.

### 2. New module `src/notificationforwarder/spool_dump.py`
A single function, e.g. `dump_spool(forwarder, tag, order, limit, fmt) -> int`, owns: path computation, opening a read-only connection, the ordered/limited SELECT, per-record decoding, formatting, and the exit code. The CLI calls it and `sys.exit`s with its return value.

- **Why**: keeps the CLI thin and makes the whole feature unit-testable without invoking the CLI or a real OMD site (tests can point `OMD_ROOT` at a temp dir and pre-populate the DB, as the existing tests do).
- **Alternative considered**: put the logic inline in `bin/notificationforwarder`. Rejected — hard to test the formatting/order/limit edges without a CLI harness.

### 3. Open the database read-only via URI, with a 1-second busy cap
Open with `sqlite3.connect("file:<db_file>?mode=ro", uri=True)` and set `busy_timeout = 1000`. If the database stays locked beyond the cap, the dump takes the unreadable-database path (non-zero exit, no record data on stdout).

- **Why**: `mode=ro` is defense-in-depth for the "strictly read-only" requirement — the connection cannot write even if a code path misbehaves. The busy timeout lets a concurrent `flush()` (which takes a writer lock via `BEGIN IMMEDIATE`) finish instead of failing the dump with `database is locked`. A plain `SELECT` holds only a shared lock and is brief.
- **Why 1 second**: the spec pins a numeric cap so the behavior is testable. A flush's write-lock holding is brief (the 30-second `submit` runs outside the SQLite transaction; the only write transactions are the short enqueue commit and the `BEGIN IMMEDIATE` prune select-and-delete), so a 1-second wait only ever covers a commit boundary — not a hang. If the lock is held longer, something is wrong and the operator wants to know.
- **Note**: this is a *read* lock, not the `fcntl` flush lock. The dump must not take the flush lock (the spec forbids it); a shared read never conflicts with a writer's exclusive acquisition for the duration of a short SELECT, and the busy timeout covers the overlap window.
- **Alternative considered**: reuse `SpoolStore` with a new method. Rejected — `SpoolStore` opens a writable connection and its identity is the write path; adding a read-only mode there muddies the `thread-safe-spool-store` contract.

### 4. Ordering and limit are pushed into SQL, after argument validation
`SELECT id, timestamp, payload FROM <table> ORDER BY timestamp <dir>, id <dir> [LIMIT ?]`, `<dir>` = `ASC`/`DESC` from `--order`, `LIMIT` only when a valid `--limit` was given. Before the query: `--order` must be `oldest` or `newest`, `--limit` an integer >= 1, `--dump-format` must be `text` or `json`, and the forwarder argument must be present in dump mode; any violation is a usage error (non-zero exit, message on stderr, no record data on stdout).

- **Why validate up front**: the two naive traps are `--limit 0` (SQLite returns zero rows — reads as a drained queue) and `--limit -1` (SQLite treats a negative LIMIT as unlimited — floods the terminal). Both are specified as usage errors by the spec, so they never reach SQL.
- **Why**: ordering by the stored `timestamp` column (not a Python sort over decoded payloads) is fast and, per the stored format, chronological; `id` as the secondary key gives a deterministic order on same-second ties. Limiting in SQL avoids fetching the whole table.
- **Alternative considered**: fetch everything and sort/limit in Python (parsing JSON for a timestamp). Rejected — slow, and the original timestamp in the JSON is a different value (event origin time) than the spool time we want.

### 5. Decode per record, isolate failures
Decode each `payload` with `json.loads` independently, wrapped so a `JSONDecodeError` marks that one record undecodable (record number + spool time + a marker plus a short raw prefix) and continues.

- **Why**: matches the codebase's existing stance that an undecodable payload must never abort processing (see the expired-payload handling in `flush()`).
- **Why a raw prefix**: gives the operator a breadcrumb without hiding the row.

### 6. Output and streams (pinned)
- **Spool time**: shown verbatim — the stored `timestamp` string `YYYY-MM-DD HH:MM:SS` (UTC). No conversion to local time, no reformatting. The text header states the unit is UTC. Rationale: the operator's 3 a.m. question is "will these survive the retention window (default 5 min)"; a free display format (local time / ISO / time-of-day) is off by the site's UTC offset and untestable. The log lines prefix `%(asctime)s` in *local* time (`util.py`), so correlation with the log is by record number, not by visual time match.
- **`text`** (default): the header on **stderr** (database path, table, order, total, shown) is written **before** the first stdout record. Stdout is exactly one physical line per record: `#<id>  <spool_time>  <payload>`, where `<payload>` is one compact single-line JSON encoding of the decoded value (`json.dumps` with `ensure_ascii=False`, so non-ASCII stays readable and control characters are escaped; the stored payloads from `enqueue` are already single-line). A decodable payload is not truncated. No pretty-printing: an indented payload would put raw newlines on stdout and split one event across lines, breaking `head` and line counts.
- **`json`**: the same header on **stderr**, and one JSON array on **stdout**, one element per record: `{ "id": <number>, "spooled_at": "<verbatim>", "payload": <decoded value> }`. Empty spool → stdout is `[]`.
- **Undecodable payload**: the record is still listed and counts toward limit/shown. JSON element: `payload: null` plus `undecodable: true` and `raw_prefix` (first 120 characters of the stored text, control characters escaped). Text: the same marker and prefix on that record's single line. Rationale: the raw prefix (120 chars is a bound so a test can pin "short") lets the operator tell a truncated JSON blob from binary; a corrupt payload can itself contain raw newlines, so the prefix must be escaped to keep the one-line invariant.
- **Totals from one snapshot**: `total` and the listed rows come from one consistent read — a single `BEGIN ... COMMIT` (deferred) transaction holding `total = COUNT(*)` and the `SELECT` inside it. Rationale: the receiver-down period is exactly when concurrent `enqueue` and flush `delete`/`move_to_end` happen, and count-then-select across two transactions can report `total=12 shown=12` for a list that is no longer the whole queue. The write transactions in the codebase are short (the 30-second `submit` runs outside SQLite), so holding a deferred read for a few `SELECT`s is not a hang risk.
- **On any non-zero exit** (usage error, unreadable DB, missing table): stdout carries no record data — a truncated JSON array or partial line list would read as a short successful dump.
- **Why stderr for the header**: keeps `--dump-format json | jq` clean; stdout carries only record data in both modes.

### 7. Exit codes
- `0`: dump succeeded, including the empty and missing-database cases (both reported as "spool empty" on stderr, with the resolved path and table named).
- Non-zero, usage error: `--dump-spool` without a forwarder argument, or an invalid `--order` / `--limit` / `--dump-format` value. Message on stderr, no record data on stdout.
- Non-zero, database error: the database could not be read (locked beyond the 1-second cap, corrupt file) or the file exists but lacks the expected table. Error on stderr naming the path (and the missing table), no record data on stdout, and never reported as "spool empty".

### 8. Where the tests live
A dedicated `tests/test_spool_dump.py` for the new `spool-inspection` capability.

- **Why not `test_resilience_spool.py`**: the `delivery-resilience` spec names that file as the layer for *resilience* edges (retry, probe, heartbeat, pruning, concurrency). Dump is an inspection feature with its own capability and its own observable contract (ordering, limit, formats, corrupt/empty handling), so it gets its own file rather than blurring the resilience layer.
- **How tests obtain data**: point `OMD_ROOT` at a temp dir (the existing test convention), pre-create the spool file/table directly with `sqlite3`, seed rows with controlled `timestamp`/`id` values, invoke `spool_dump.dump_spool(...)`, and assert stdout/stderr/exit-code. A corrupt row is seeded by writing a non-JSON `payload`.

## Risks / Trade-offs

- **[A reader briefly overlaps a writer]** → `mode=ro` + `busy_timeout` keeps the dump safe and non-destructive; worst case the dump reports "locked" and exits 1, which the operator can retry.
- **[Dump output can be large]** → `--limit` bounds it; the full-dump default is intentional (the operator asked to see everything) and they can pipe through `head`/`jq` since streams are separated.
- **[Record number drifts after `move_to_end`]** → expected and fine: `id` is the log-correlation key and the stored `timestamp` is the stable "when spooled" value the spec orders by; both are shown, so nothing is lost.
- **[Two forwarder instances could share a table name if tags collide]** → not a new risk; the path/table naming is unchanged and the dump uses the exact same naming the write path uses.
- **[Secrets in payload]** → the payload is the stored event (host/service/state), not credentials; consistent with what the spool already holds on disk. No new exposure beyond the file itself.

## Migration Plan

None required. Additive CLI flags with safe defaults; no schema or stored-data change. Rollback is removing the change. Existing spool databases work unmodified because the dump only reads the existing three columns.

## Open Questions

- Exact wording of the undecodable marker text and the header labels — cosmetic, decide in implementation. The behavior is pinned by the spec (verbatim spool time, one line per record, `null`/`undecodable`/`raw_prefix` in JSON, 120-char prefix, summary before rows).
