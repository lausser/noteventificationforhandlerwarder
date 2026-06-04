## Why

`notificationforwarder` currently prints a noisy `pynostr` websocket warning during Nostr startup, even though the forwarder still works. That creates avoidable operator noise and makes it harder to spot real delivery problems.

## What Changes

- Prevent the known `websocket_ping_timeout` warning from appearing during Nostr forwarder startup.
- Keep Nostr delivery behavior unchanged for normal notification publishing.
- Preserve the existing fail-fast behavior if `pynostr` is unavailable.
- **BREAKING**: none.

## Capabilities

### New Capabilities

- 

### Modified Capabilities

- `nostr-notificationforwarder`: the Nostr forwarder should initialize without emitting the known websocket timeout warning in normal use.

## Impact

- Affects the `notificationforwarder` Nostr forwarder implementation and its startup path.
- May involve a small adjustment to websocket timeout handling or narrow output suppression around `pynostr` initialization.
- Adds or updates regression coverage for startup noise.
