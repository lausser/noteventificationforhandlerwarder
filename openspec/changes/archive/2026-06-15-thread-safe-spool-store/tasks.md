## 1. Make SpoolStore thread-safe

- [x] 1.1 Add `import threading` to `notificationforwarder/src/notificationforwarder/spool.py`
- [x] 1.2 Add `self._lock = threading.Lock()` in `SpoolStore.__init__`
- [x] 1.3 Wrap `init_db` body in `with self._lock:`
- [x] 1.4 Wrap `count` body in `with self._lock:` (return inside the block)
- [x] 1.5 Wrap `enqueue` body in `with self._lock:`
- [x] 1.6 Wrap `prune_expired` body in `with self._lock:` (return inside the block)
- [x] 1.7 Wrap `fetch_batch` body in `with self._lock:` (return inside the block)
- [x] 1.8 Wrap `delete` body in `with self._lock:`
- [x] 1.9 Wrap `commit` body in `with self._lock:`
- [x] 1.10 Wrap `close` body in `with self._lock:`

## 2. Update test

- [x] 2.1 Rewrite `test_concurrent_enqueue_shared_instance` to assert `errors == []` and `store.count() == 20`
- [x] 2.2 Update docstring to reflect that concurrent enqueue is now serialized and safe

## 3. Verification

- [x] 3.1 Run the previously-crashing test on Python 3.14: `OMD_SITE=my_devel_site pytest "tests/test_resilience_spool.py::TestSpoolStore::test_concurrent_enqueue_shared_instance" -v`
- [x] 3.2 Run full test suite on Python 3.14: `OMD_SITE=my_devel_site pytest tests/ -v`
- [x] 3.3 Run full test suite on a supported version (e.g. 3.12) to confirm no regression
