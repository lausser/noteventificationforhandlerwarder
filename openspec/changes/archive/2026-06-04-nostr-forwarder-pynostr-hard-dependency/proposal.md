## Why

The Nostr forwarder should depend on `pynostr` directly instead of carrying a local fallback implementation. If the library is missing, the forwarder should fail fast and let the existing baseclass error handling log and stop the run.

## What Changes

- Remove the local fallback shims from the Nostr forwarder.
- Treat `pynostr` as a required runtime dependency for the Nostr forwarder.
- Keep the current baseclass failure handling path so import failures are reported once at startup or first use.
- Preserve existing Nostr DM behavior for valid environments.

## Capabilities

### New Capabilities
- `nostr-forwarder-pynostr-hard-dependency`: enforce a hard dependency on `pynostr` and simplify the forwarder to use the real library only.

### Modified Capabilities
- `nostr-notificationforwarder`: clarify that the Nostr forwarder must not substitute its own fallback classes when `pynostr` is unavailable.

## Impact

Affected code is limited to the Nostr formatter/forwarder implementation and its tests. The runtime dependency story becomes simpler, and failure mode is reduced to the existing import error path handled by the baseclass.
