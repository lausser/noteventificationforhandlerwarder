# Design

## Context

Motivation: see proposal.md (Why). Requirements: see `specs/delivery-resilience`.

Each notification runs in its own short-lived process. `forward_formatted()` flushes the spool first if it is not empty and `probe()` succeeds. The flush runs under a non-blocking fcntl lock. Then the process submits the live event, which is spooled only if that submit fails. Since `bound-spool-flush-replay`, `flush()` walks the rows up to a snapshot of the highest id, tries each row once, and stops after a batch of 10 without progress.

The spool table uses `INTEGER PRIMARY KEY` without `AUTOINCREMENT`. A new row gets the highest id plus one, so after the last row is deleted its id can be reused. A reused id is always the highest id in the table.

## Goals / Non-Goals

**Goals:**
- At most one failed submit per flush.
- A permanently rejected event cannot block the backlog for its whole retention time.
- Keep the existing logs, summary counters and the default delivery path.

**Non-Goals:**
- Per-event attempt counters or a dead-letter table (both need a schema change).
- Detecting permanent rejections inside forwarder plugins.

## Decisions

**1. Stop the flush at the first failed replay.**
In `flush()`, a failed submit (False, a failure dict, or an exception, including the submit timeout) ends the walk immediately. The flush logs "event stays in spool" for that row, then the existing critical "spooled events could not be submitted" with `spooled_count = count(max_id=snapshot)`, then the summary. The per-batch progress check becomes unnecessary and is removed. Discarded and unformattable rows are still deleted and do not stop the walk.
- Alternative considered: stop only on timeouts and continue after a fast failure. Rejected: many forwarders catch their own connection errors and timeouts and just return False, so the baseclass cannot reliably tell the two apart.

**2. Remember where the flush stopped.**
`flush()` sets `self.flush_stopped_at` to the id of the failed row, or `None`. It is reset at the start of every flush. The flush lock is released at the end of the flush, as today, so the long live submit does not hold it.

**3. Use a successful live submit as the signal that the receiver is up.**
After `submit()` of the live event succeeds in `forward_formatted()` and `flush_stopped_at` is set, the process calls `move_stopped_event_to_end()`. That covers every successful submit, heartbeats included, because they also prove that the receiver is up. A live event that is discarded, incomplete or failing never calls `submit()` successfully, so nothing moves.
- Alternative considered: move the event right away when it fails. Rejected: during an outage every head event would rotate, which reorders the backlog for nothing.
- Alternative considered: count failures per event. Rejected: during an outage the counters cannot tell an outage from a bad event, and they need a new column.

**4. Move under the flush lock, in one transaction.**
`move_stopped_event_to_end()` opens the lock file and tries the lock once (`acquire_lock_with_retry(..., max_attempts=1)`). If the lock is not available, it logs at debug level and gives up; a later flush that stops at the same event will try again. With the lock held, it calls `SpoolStore.move_to_end(event_id)`, which does the following under the instance thread lock and commits once:

```sql
INSERT INTO t(payload, timestamp)
  SELECT payload, timestamp FROM t
  WHERE id = :id AND id < (SELECT MAX(id) FROM t);
-- only if the insert added a row (cursor.rowcount == 1):
DELETE FROM t WHERE id = :id;
```

It returns the new id (`lastrowid`), or `None` if nothing was moved.
- **Copying the timestamp** keeps the original spool time, so `prune_expired()` still drops the event on schedule.
- **The `id < MAX(id)` condition** skips an event that is already last. It also covers a reused id: if another process delivered the event and a new event got the same id, that id is the highest one and is never moved.
- **Holding the flush lock** means no flush has this row in memory while it is being moved. Without the lock, a concurrent flush could deliver the old row, delete the old id, and leave the moved copy behind as a duplicate.

**5. Logging.**
A move logs critical "spooled event moved to the end of the spool" with `event_id`, `new_event_id` and `action: moved_to_end`. The text logger gets a message for the new action (`event 7 was rejected while the receiver accepts other events and moved to the end of the spool as 31`). The JSON logger only writes known context keys, so `new_event_id` is added to them.

## Risks / Trade-offs

- [A temporary failure of the head event (a one-time network hiccup) followed by a successful live submit moves that event to the end, so it arrives after newer events.] → Order was never guaranteed (see the README's "Delivery Order"). The move is logged, and the event is still delivered.
- [The live event might go to a different endpoint than the stopped event, via a per-event `forwarderopts` override, so its success may not prove that the stopped event's receiver is up.] → In the worst case a temporarily undeliverable event moves to the end; nothing is lost.
- [A permanently rejected event keeps cycling to the end until it expires, with one failed submit and one critical log per cycle.] → This is intended: it is visible in the logs and bounded by `max_spool_minutes`.
- [With the receiver up, a stopped flush now leaves later events in the spool until the next notification, where the old rule would have continued.] → After the move, the next flush delivers them. Heartbeats make that happen regularly.

## Migration Plan

No schema or configuration change. Deploy by upgrading the package. Rollback is a plain revert; spool databases stay compatible in both directions.
