# Tasks

## 1. Stop at the first failed replay

- [x] 1.1 In `flush()` (`notificationforwarder/src/notificationforwarder/baseclass.py`), stop the walk at the first failed submit, remove the per-batch progress check, keep "event stays in spool", the critical stuck log with `count(max_id=snapshot)` and the summary; set `self.flush_stopped_at`. Verify with new tests for `flush-stops-at-first-failed-replay`, `flush-stops-after-successful-replays`, `flush-stops-on-submit-timeout` and `flush-continues-after-trash`
- [x] 1.2 Adapt the existing tests to the new rule and verify that they pass: `test_flush_terminates_while_other_processes_spool` (only event 0 submitted, 13 rows, stuck `spooled_count` 12), `test_flush_beyond_batch_limit_stuck_detection` (11 succeed, the 12th fails: attempted=12, recovered=11, stayed_in_spool=1), `test_persistent_failure_keeps_row_and_terminates` (unchanged expectations, rerun)
- [x] 1.3 Update `notificationforwarder/tests/TESTS.md` for the changed and new tests; verify that every test name appears there

## 2. Move a rejected event to the end

- [x] 2.1 Add `SpoolStore.move_to_end(event_id)` (`notificationforwarder/src/notificationforwarder/spool.py`): one transaction under the thread lock, keeps payload and timestamp, skips an event that is gone or already last, returns the new id or `None`. Verify with `TestSpoolStore` tests for: moved behind all rows with the same timestamp; already last; gone; and that another connection can insert right afterwards (no open transaction)
- [x] 2.2 Add `move_stopped_event_to_end()` to the forwarder and call it from `forward_formatted()` after a successful live submit; take the flush lock with one attempt. Verify with tests for `rejected-event-moves-to-end`, `no-move-when-live-submit-fails`, `no-move-without-live-submit`, `heartbeat-success-moves-rejected-event`, `no-move-while-another-process-flushes` (lock held by a child process, as in `test_flush_is_suppressed_while_another_process_holds_the_lock`), `no-move-when-event-is-already-last` and `moved-event-still-expires`
- [x] 2.3 Add the text-logger message for `action: moved_to_end` (`notificationforwarder/src/notificationforwarder/text/logger.py`) and `new_event_id` to the JSON logger; verify with a test in `notificationforwarder/tests/test_loggers.py` for the text and JSON output
- [x] 2.4 Update `notificationforwarder/tests/TESTS.md` for the new tests; verify that every test name appears there

## 3. Documentation

- [x] 3.1 Update "Spool Flushing" and "Delivery Order" in `notificationforwarder/README.md` and `notificationforwarder/INDEX.md`: the flush stops at the first failure; a rejected event moves to the end once another event gets through; remove the case "a later spooled event succeeds after a failed one" from the order section and add the move as a new case. Verify that both files contain the same text

## 4. Integration checks

- [x] 4.1 Run `OMD_SITE=my_devel_site python3 -m pytest tests/` in `notificationforwarder`: all tests pass (nostr tests skipped without `nostr_sdk`)
- [x] 4.2 Run `uvx flake8 --max-line-length=120` on the changed files: no new findings compared with HEAD
- [x] 4.3 Rerun the ordering reproduction (`order/repro_order.py` in the scratchpad) and record the delivered order with the new rule: `4-PROBLEM, 2-ACK, 3-RECOVERY, 1-PROBLEM, 5-RECOVERY` (before: `2-ACK, 3-RECOVERY, 4-PROBLEM, 1-PROBLEM, 5-RECOVERY`)
- [x] 4.4 Run `openspec validate stop-flush-at-first-failure --strict`

## Workflow follow-up

- Commit the implementation and the OpenSpec change after review.
- Archive the change with `openspec archive stop-flush-at-first-failure`, then verify that `openspec/specs/delivery-resilience/spec.md` contains the modified and added requirements.
