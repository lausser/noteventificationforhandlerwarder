# Tasks

## 1. Commit pruning immediately

- [x] 1.1 In `notificationforwarder/src/notificationforwarder/spool.py`, commit inside `prune_expired()` (return the rowcount captured before the commit); verify with `test_prune_expired_does_not_hold_write_lock` in `notificationforwarder/tests/test_resilience_spool.py` (fails with `database is locked` on the old code, passes now)
- [x] 1.2 Add the test to the `TestSpoolStore` table in `notificationforwarder/tests/TESTS.md`

## 2. Bounded spool replay

- [x] 2.1 Add `SpoolStore.max_id()`, the optional `after_id` / `max_id` parameters to `fetch_batch()` and an optional `max_id` to `count()`; verify that the existing `fetch_batch` tests (`test_fetch_batch_limit`, `test_fetch_batch_limit_zero`, `test_fetch_batch_limit_exceeds_total`) pass unchanged
- [x] 2.2 Rewrite the `flush()` loop in `notificationforwarder/src/notificationforwarder/baseclass.py` to walk rows up to the snapshot id by id and stop after a batch without progress; verify with `test_persistent_failure_keeps_row_and_terminates` and `test_flush_beyond_batch_limit_stuck_detection` (unchanged, passing)
- [x] 2.3 Add `test_flush_terminates_while_other_processes_spool`, including that the stuck log's `spooled_count` is 12 (snapshot rows) rather than 22 (live queue); verify it fails against the old `flush()` (endless loop, stopped by the test's `SystemExit` guard) and passes now
- [x] 2.4 Add the test to the `TestSpoolReplayEdges` table in `notificationforwarder/tests/TESTS.md`

## 3. Integration checks

- [x] 3.1 Run `pytest tests/` in `notificationforwarder`: 210 passed, 13 skipped (nostr tests, `nostr_sdk` not installed)
- [x] 3.2 Run `flake8 --max-line-length=120` on the changed files: no new findings compared with HEAD (rechecked after the review fixes)
- [x] 3.3 Rerun the production-scenario repro (failing submits plus concurrent spooling): flush ends after 10 submits and concurrent spooling succeeds
- [x] 3.4 Run `openspec validate bound-spool-flush-replay --strict`

## Workflow follow-up

- Commit the code fix and the OpenSpec change after review.
- Archive the change with `openspec archive bound-spool-flush-replay`, then verify that `openspec/specs/delivery-resilience/spec.md` and `openspec/specs/thread-safe-spool-store/spec.md` contain the updated requirements.
