# Tasks

## 1. Log the queue length after every flush

- [x] 1.1 In `flush()` (`notificationforwarder/src/notificationforwarder/baseclass.py`), log "spooling queue length" with `queue_length = spool_store.count()` at info level after the replay summary; verify with tests for `queue-length-zero-after-drain`, `queue-length-after-stopped-flush`, `queue-length-includes-concurrently-spooled-events`, `queue-length-not-logged-without-lock` and `queue-length-json-format` in `notificationforwarder/tests/test_resilience_spool.py`
- [x] 1.2 Add the tests to `notificationforwarder/tests/TESTS.md`; verify that every test name appears there
- [x] 1.3 Document the line for monitoring in "Spool Flushing" of `notificationforwarder/README.md` and `notificationforwarder/INDEX.md`, including the database query for a check without notifications; verify that both files contain the same text

## 2. Integration checks

- [x] 2.1 Run `OMD_SITE=my_devel_site python3 -m pytest tests/` in `notificationforwarder`: all tests pass (nostr tests skipped without `nostr_sdk`)
- [x] 2.2 Run `uvx flake8 --max-line-length=120` on the changed files: no new findings compared with HEAD
- [x] 2.3 Run `openspec validate log-queue-length-after-flush --strict`

## Workflow follow-up

- Archive with `openspec archive log-queue-length-after-flush`, commit, release 4.6.1.
