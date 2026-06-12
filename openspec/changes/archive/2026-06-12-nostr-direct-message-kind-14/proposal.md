## Why

The current Nostr implementation is built around `pynostr`, which exposes NIP-04-style direct messages and does not provide a clean path to NIP-17 private messages. We need a library-backed way to publish proper NIP-17 direct messages so notificationforwarder can interoperate with modern Nostr clients and avoid protocol drift.

## What Changes

- Replace the current Nostr DM implementation with `nostr-sdk` Python bindings.
- Use the library's NIP-17 private-message APIs instead of hand-assembling encrypted DM events.
- Keep the notificationforwarder formatter/forwarder pipeline intact where possible, but adapt it to the new library's client model.
- Update dependency, packaging, and test coverage to reflect the new backend.
- Document the alpha-state dependency and its operational risks.

## Capabilities

### New Capabilities
- `nostr-sdk-nip17-private-messages`: Nostr notificationforwarder can publish NIP-17 private messages through `nostr-sdk`.

### Modified Capabilities

## Impact

- Affects the Nostr formatter/forwarder implementation, dependency metadata, and tests.
- Likely introduces an async/native dependency path via `nostr-sdk` / `nostr-sdk-ffi`.
- No user-facing CLI changes are expected, but runtime installation and compatibility characteristics will change.
