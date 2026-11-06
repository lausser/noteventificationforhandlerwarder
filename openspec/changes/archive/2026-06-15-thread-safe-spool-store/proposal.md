## Why

Running `pytest` on Python 3.14 crashes the test process with a segmentation fault (exit code 139). The crash is caused by two threads calling `enqueue()` on a shared `SpoolStore` instance, which uses a single `sqlite3` connection/cursor opened with `check_same_thread=False`. On Python ≤3.12 this raised a catchable `sqlite3.ProgrammingError`; on 3.14 it faults inside the `_sqlite3` C extension. Python 3.14 has been added to the GitHub Actions CI matrix, so CI now fails and the crash must be fixed.

## What Changes

- Add a per-instance `threading.Lock` to `SpoolStore` and serialize all methods that touch the shared `sqlite3` connection/cursor.
- Update the test `test_concurrent_enqueue_shared_instance` to assert the now-deterministic safe outcome (all writes succeed, `count() == 20`) instead of expecting a catchable error.
- No changes to method signatures, SQL, return types, or the `fcntl`-based cross-process flush lock.

## Capabilities

### New Capabilities
- `thread-safe-spool-store`: Thread-safe access to `SpoolStore` via per-instance locking, enabling safe concurrent `enqueue()` calls from multiple threads on a shared instance.

### Modified Capabilities

## Impact

- **Code**: `notificationforwarder/src/notificationforwarder/spool.py` — add `import threading`, add `self._lock` in `__init__`, wrap method bodies in `with self._lock:`.
- **Tests**: `notificationforwarder/tests/test_resilience_spool.py` — rewrite `test_concurrent_enqueue_shared_instance`.
- **CI**: GitHub Actions matrix (3.9–3.14) should go green on 3.14 after this change.
- **Dependencies**: None new; `threading` is stdlib.
- **Production behavior**: Unchanged — the lock is uncontended on the single-thread production path.
