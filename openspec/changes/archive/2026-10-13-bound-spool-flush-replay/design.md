# Design

## Context

Motivation: see proposal.md (Why). Requirements: see `specs/delivery-resilience` and `specs/thread-safe-spool-store`.

Each notification is handled by its own short-lived notificationforwarder process. When the spool is non-empty and `probe()` succeeds, `forward_formatted()` calls `flush()` before submitting the new event. `flush()` takes a non-blocking fcntl lock (3 attempts, ~0.4 s); losers log "concurrent flush suppressed" and continue with their own submit, spooling the event if it fails. The spool is a SQLite table with an autoincrement `id`, opened with Python `sqlite3` in its default (legacy) transaction mode, which implicitly opens a transaction before any DML statement.

## Goals / Non-Goals

**Goals:**
- A bounded replay whose duration depends only on the spool contents at flush start.
- No open write transaction while the flusher waits on submit timeouts.
- Keep logs, replay/discard/trash handling and summary counters as they are.

**Non-Goals:**
- A background or time-driven flusher.
- Changes to the lock protocol, timeouts or batch size.

## Decisions

**1. Snapshot the highest id at flush start and walk forward by id.**
`flush()` reads `max_id()` once after pruning and repeatedly calls `fetch_batch(after_id=last_id, max_id=snapshot_max_id)`, advancing `last_id` past every row it has handled, failed or not.
- Each row is attempted at most once, and rows spooled concurrently (with larger ids) are ignored.
- Alternatives considered:
  - Keep the count comparison and add a round limit or time budget. Rejected: this still retries the same failing head batch until the limit runs out, and choosing the limit is arbitrary.
  - Compare per-pass deletions but keep re-reading the head (`ORDER BY id LIMIT 10`). Rejected: with mixed success and failure, failing rows are retried on every pass, and concurrent arrivals keep the loop alive.

**2. Stop after the first batch without progress.**
Progress means at least one row was replayed successfully or deleted (discarded or trash). A batch that only fails means the destination is still unhealthy, so walking the rest of the snapshot would only cost more timeouts. The existing critical "spooled events could not be submitted" log is kept. Its `spooled_count` is the number of snapshot rows still in the spool (`count(max_id=snapshot)`), not the live queue size, which would include rows spooled concurrently that this flush never attempted.

**3. Commit inside `prune_expired()`.**
This is the smallest change that ends the implicit transaction.
- Alternative considered: switching the connection to autocommit (`isolation_level=None`). Rejected: it changes transaction semantics for every `SpoolStore` method and is out of scope.

**4. Extend `fetch_batch()` and `count()` with optional parameters instead of adding new methods.**
The defaults (`after_id=0`, `max_id=None`) produce the same rows as before, so existing callers and tests are unaffected. This is why the `thread-safe-spool-store` "unchanged API" requirement is relaxed to "backward compatible" rather than broken.

## Risks / Trade-offs

- [Events spooled during a flush wait for the next flush, which only happens when the next notification arrives.] → This is the same passive model as before. Retention (`max_spool_minutes`) still bounds how long they are kept.
- [With alternating successes and failures, a flush can still walk the whole snapshot, which costs up to snapshot size × submit timeout.] → The cost is bounded and every row is tried only once. A batch that fails completely ends the flush early.
- [The "spooled events to be re-sent" log now shows the batch size, not the total spool size.] → Total queue length is still logged by "spooling queue length".

## Migration Plan

No schema or configuration change. Deploy by upgrading the package. Rollback is a plain revert; spool databases remain compatible in both directions.
