## 1. Fix flush loop discard handling

- [x] 1.1 Add `is_discarded` check in `notificationforwarder/src/notificationforwarder/baseclass.py` flush loop after `format_event()` — skip and delete discarded events with an info log
- [x] 1.2 Update `test_discarded_event_deleted_with_trash_log` in `notificationforwarder/tests/test_resilience_spool.py` to expect the new behavior (discarded events are skipped, not submitted)

## 2. Reset no_more_logging flag at flush start

- [x] 2.1 Add `self.baseclass_logs_summary = True` at the start of `flush()` in `baseclass.py` (after lock acquisition)
- [x] 2.2 Add test in `notificationforwarder/tests/test_resilience_spool.py` that verifies summary logging resumes after flush (forward after flush logs the baseclass summary)

## 3. Add shared SpoolStore threading test

- [x] 3.1 Add test in `notificationforwarder/tests/test_resilience_spool.py` that creates a single `SpoolStore` instance shared across two threads, each enqueuing 10 events, and verifies 20 rows with no corruption

## 4. Verify

- [x] 4.1 Run notificationforwarder test suite to verify all changes pass
