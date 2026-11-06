# Proposal

## Why

A production notificationforwarder (remedy, 2026-09-09) logged a flood of "flush lock failed" / "concurrent flush suppressed" while Remedy submits timed out and the spool kept growing. Two defects in spool replay turn a slow destination into a long-lasting lock-out:

1. **Flush can hold the flush lock indefinitely.** The flush loop decides "no progress" by comparing the *total* spool count between rounds and always re-reads the first 10 rows (`ORDER BY id LIMIT 10`). Concurrent notification processes that miss the lock spool their own (timed-out) events, which changes the count, so the flusher believes it made progress and retries the same failing head batch again — paying the submit timeout for every event, round after round. `prune_expired()` runs only once, so those rows never expire while the loop runs.
2. **`prune_expired()` leaves the spool write-locked.** Its DELETE is not committed; Python's `sqlite3` keeps the implicit transaction open, so the spool database stays write-locked until the first successful replay commits. While every replay fails, concurrent processes cannot spool and fail with `database is locked` after the 5 s busy timeout ("delivery failed and event could not be persisted").

## What Changes

- `flush()` replays only the rows that existed when the flush started (snapshot of the highest id) and walks through them by id, so each row is attempted at most once per flush. Rows spooled concurrently are left for the next flush.
- Stuck detection is based on per-batch progress: a batch in which no row was replayed or deleted ends the flush with the existing critical "spooled events could not be submitted" log.
- "spooled events to be re-sent" logs the size of the batch being replayed instead of the total spool size.
- `SpoolStore.prune_expired()` commits immediately.
- The critical "spooled events could not be submitted" log counts only the rows of this flush's snapshot that are still spooled, not rows spooled concurrently.
- `SpoolStore` gains `max_id()`; `fetch_batch()` gains optional `after_id` and `max_id` parameters, `count()` an optional `max_id` (defaults keep the previous behavior).

## Non-goals

- Changing the fcntl flush lock, its retry/backoff, or the probe gating.
- Changing submit timeouts, batch size, or retention (`max_spool_minutes`).
- WAL mode or other SQLite tuning.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `delivery-resilience`: flush replay is bounded to a snapshot of the spool, each row is attempted at most once per flush, stuck detection is per-batch progress instead of an unchanged total count, and pruning must not block concurrent spooling.
- `thread-safe-spool-store`: the "API and SQL unchanged" requirement is relaxed to backward-compatible extensions (`max_id()`, optional `fetch_batch()` / `count()` parameters, commit in `prune_expired()`).

## Impact

- **Code**: `notificationforwarder/src/notificationforwarder/baseclass.py` (`flush()`), `notificationforwarder/src/notificationforwarder/spool.py` (`prune_expired`, `max_id`, `fetch_batch`, `count`)
- **Tests**: `notificationforwarder/tests/test_resilience_spool.py` (two regression tests)
- **Dependencies**: none
- **Behavior**: events spooled while a flush is running are replayed by the next flush instead of the running one. No breaking API changes.
