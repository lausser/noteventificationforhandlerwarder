## MODIFIED Requirements

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
