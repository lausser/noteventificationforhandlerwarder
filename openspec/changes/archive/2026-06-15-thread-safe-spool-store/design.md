## Context

`SpoolStore` (in `notificationforwarder/src/notificationforwarder/spool.py`) manages a per-forwarder SQLite database for retrying failed notification submissions. It holds a single `sqlite3.Connection` and `Cursor` opened with `check_same_thread=False`. In production, a `SpoolStore` is used by exactly one thread per process, so this is safe. However, a test (`test_concurrent_enqueue_shared_instance`) deliberately drives two threads against a shared instance to document the limitation — on Python ≤3.12 this raised a catchable `ProgrammingError`, but on Python 3.14 it segfaults inside the `_sqlite3` C extension.

## Goals / Non-Goals

**Goals:**
- Make `SpoolStore` thread-safe so concurrent calls from multiple threads on a shared instance are serialized and deterministic.
- Fix the Python 3.14 segfault in CI.
- Minimal change: add a lock, wrap method bodies, update the test.

**Non-Goals:**
- Refactoring `SpoolStore` beyond adding the lock.
- Changing the single-connection design or `check_same_thread=False` setting.
- Changing the `fcntl`-based cross-process flush lock (unrelated).
- Optimizing lock granularity or introducing connection pooling.

## Decisions

### Use a per-instance `threading.Lock`

**Choice**: Add `self._lock = threading.Lock()` in `__init__` and wrap every DB-touching method body in `with self._lock:`.

**Rationale**: This is the smallest correct change. A `threading.Lock` (non-reentrant) is sufficient because no method calls another while holding the lock. Per-instance means independent `SpoolStore` objects (the normal production case) never contend.

**Alternatives considered**:
- *Remove the test / exclude 3.14 from CI*: Defeats the purpose; 3.14 is now a supported target.
- *Use `sqlite3` connection per thread*: Over-engineered, changes the single-connection design, risks data races on the same DB file without WAL.
- *Use `threading.RLock`*: Unnecessary — no method re-acquires the lock. Slightly more overhead for no benefit.
- *Use a module-level lock*: Would serialize all `SpoolStore` instances globally, creating unnecessary contention.

### Wrap `open()` is optional

**Choice**: Do NOT wrap `open()` in the lock. It is called once before threads start.

**Rationale**: `open()` is an initialization method. Adding the lock there adds no safety value and could mask initialization bugs.

### Methods that return values: return inside the lock

**Choice**: For `count()`, `prune_expired()`, `fetch_batch()`, capture the result and return it inside the `with self._lock:` block.

**Rationale**: Returning after releasing the lock would allow the returned value to be stale if another thread mutates the store immediately after. Keeping the read inside the lock ensures consistency.

## Risks / Trade-offs

- **Lock contention in high-throughput scenarios**: Production uses a single thread, so the lock is uncontended. If future multi-threaded usage emerges, the lock becomes a serialization point. Mitigation: acceptable for now; can revisit if profiling shows it matters.
- **Test changes mask future regressions**: The updated test now asserts success, which is the correct behavior. The original "limitation documentation" test is no longer needed since the limitation is removed.
