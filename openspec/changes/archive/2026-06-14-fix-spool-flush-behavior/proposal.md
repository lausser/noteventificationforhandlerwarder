## Why

Three issues in the spool flush subsystem reduce reliability and testability:

1. **Flush replays discarded events.** The flush loop in `baseclass.py` checks `if formatted_event:` but never checks `is_discarded`. A discarded event that was spooled will be re-submitted on every flush cycle and never deleted — wasting resources and potentially delivering unwanted notifications.

2. **`no_more_logging()` is a permanent one-way switch.** `forward_formatted()` calls `no_more_logging()` after every successful submission, permanently silencing the baseclass summary log. Operators lose visibility after the first successful delivery. The flag should reset at the start of each flush cycle.

3. **SpoolStore threading test uses separate instances.** `test_concurrent_enqueue` creates two independent `SpoolStore` instances, which doesn't test the real scenario of a shared instance across threads.

## What Changes

- Add `is_discarded` check in the flush loop: skip and delete discarded events instead of re-submitting them.
- Reset `self.baseclass_logs_summary = True` at the start of `flush()` so the summary log is restored after replay.
- Update `test_discarded_event_deleted_with_trash_log` to expect the new behavior (discarded events are skipped, not submitted).
- Add a test that shares a single `SpoolStore` instance across two threads to verify real concurrent behavior.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `delivery-resilience`: The flush loop now skips discarded events instead of replaying them. The `no_more_logging` flag is reset at the start of flush.

## Impact

- **Code**: `notificationforwarder/src/notificationforwarder/baseclass.py` (flush loop logic)
- **Tests**: `notificationforwarder/tests/test_resilience_spool.py` (update existing test, add new threading test)
- **Dependencies**: none
- **Breaking changes**: none — discarded events were never supposed to be replayed
