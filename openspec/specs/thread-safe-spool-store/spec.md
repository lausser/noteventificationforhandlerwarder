### Requirement: SpoolStore shall be thread-safe for concurrent access
`SpoolStore` SHALL serialize all operations that touch the shared `sqlite3` connection/cursor using a per-instance `threading.Lock`. Concurrent calls to any DB-touching method from multiple threads on the same `SpoolStore` instance SHALL execute sequentially without errors or data corruption.

#### Scenario: Concurrent enqueue on shared instance
- **WHEN** two threads call `enqueue()` concurrently on the same `SpoolStore` instance with 10 events each
- **THEN** all 20 events are stored and `count()` returns 20

#### Scenario: Concurrent mixed operations on shared instance
- **WHEN** one thread calls `enqueue()` while another calls `fetch_batch()` on the same `SpoolStore` instance
- **THEN** both operations complete without errors and the fetch returns consistent results

#### Scenario: Lock does not affect independent instances
- **WHEN** two separate `SpoolStore` instances are used by different threads
- **THEN** operations on each instance proceed independently without contention

### Requirement: Existing API and behavior shall be preserved
All public method signatures, return types, SQL queries, and the `fcntl`-based cross-process flush lock SHALL remain unchanged. The `check_same_thread=False` setting on the `sqlite3` connection SHALL be retained.

#### Scenario: Single-thread production path unchanged
- **WHEN** a `SpoolStore` is used by a single thread (the production case)
- **THEN** behavior is identical to before the change — same method signatures, same return values, same performance

#### Scenario: flush() cross-process lock unaffected
- **WHEN** `flush()` is called via `acquire_lock_with_retry`
- **THEN** the `fcntl`-based file lock mechanism operates as before
