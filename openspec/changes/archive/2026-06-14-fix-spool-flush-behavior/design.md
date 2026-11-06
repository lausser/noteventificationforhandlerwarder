## Context

The flush loop in `notificationforwarder/src/notificationforwarder/baseclass.py:414-509` replays spooled events. Currently:

1. Line 452 checks `if formatted_event:` — this is truthiness, not a discard check. A discarded event (where `is_discarded=True`) still gets submitted.
2. `no_more_logging()` (line 511-515) sets `self.baseclass_logs_summary = False` permanently. It's called after every successful `forward_formatted()`, silencing the baseclass summary log forever.
3. `test_concurrent_enqueue` in `test_resilience_spool.py` creates two separate `SpoolStore` instances instead of sharing one across threads.

## Goals / Non-Goals

**Goals:**
- Skip and delete discarded events during flush instead of re-submitting them.
- Reset `baseclass_logs_summary` to `True` at the start of `flush()` so summary logging is restored after replay.
- Add a test that shares a single `SpoolStore` across two threads.

**Non-Goals:**
- Adding proactive spool flushing (passive flush on next event is acceptable).
- Changing the SpoolStore to use WAL mode or connection pooling.
- Refactoring the flush loop structure.

## Decisions

**1. Add `is_discarded` check after `format_event` in the flush loop.**

After `formatted_event = self.format_event(raw_event)` (line 451), add:
```python
if formatted_event and formatted_event.is_discarded:
    deleted_trash += 1
    logger.info("discard spooled event during replay", {
        'event_id': id,
        'action': 'discard_during_replay'
    })
    self.spool_store.delete(id)
    continue
```

This treats discarded events as trash (same as `formatted_event is None`) and deletes them from the spool.

**2. Reset `baseclass_logs_summary` at the start of `flush()`.**

At the beginning of `flush()`, after acquiring the lock:
```python
self.baseclass_logs_summary = True
```

This ensures the summary log is restored after replay, so operators see the "forwarded sum: ..." message on the next successful forward.

**3. Use a shared `SpoolStore` instance in the threading test.**

Create one `SpoolStore` instance, pass it to two threads, and verify both can enqueue concurrently without corruption.

## Risks / Trade-offs

**Risk:** Resetting `baseclass_logs_summary` at flush start means the summary log reappears after flush. This is the desired behavior — operators should see that the system is recovering.

**Risk:** The `is_discarded` check changes the flush loop's contract. The existing test `test_discarded_event_deleted_with_trash_log` currently expects discarded events to be submitted and deleted. This test must be updated to expect the new behavior (skipped and deleted without submission).
