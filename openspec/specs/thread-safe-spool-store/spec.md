## Purpose

Allow a single `SpoolStore` instance to be shared safely between threads of one notificationforwarder process, without changing how the spool behaves for single-threaded callers.

## Requirements

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
All public method signatures and return types SHALL remain backward compatible: existing calls SHALL keep working with unchanged results, and new parameters SHALL be optional with defaults that preserve the previous behavior. New methods MAY be added. The `fcntl`-based cross-process flush lock SHALL remain unchanged. The `check_same_thread=False` setting on the `sqlite3` connection SHALL be retained.

#### Scenario: Single-thread production path unchanged
- **WHEN** a `SpoolStore` is used by a single thread (the production case)
- **THEN** existing calls behave as before — same method signatures, same return values, same performance

#### Scenario: fetch_batch without new parameters is unchanged
- **WHEN** `fetch_batch()` or `fetch_batch(limit)` is called without the optional `after_id` / `max_id` parameters
- **THEN** it returns the oldest spooled events ordered by id, up to `limit`, exactly as before

#### Scenario: count without max_id is unchanged
- **WHEN** `count()` is called without the optional `max_id` parameter
- **THEN** it returns the number of all spooled events, exactly as before

#### Scenario: prune_expired does not leave a write transaction open
- **WHEN** `prune_expired()` returns
- **THEN** its deletion is committed and another connection can insert into the spool immediately

#### Scenario: flush() cross-process lock unaffected
- **WHEN** `flush()` is called via `acquire_lock_with_retry`
- **THEN** the `fcntl`-based file lock mechanism operates as before
