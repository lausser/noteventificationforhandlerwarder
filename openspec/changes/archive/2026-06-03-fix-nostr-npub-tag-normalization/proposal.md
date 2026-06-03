## Why

The Nostr plugin already lets operators exchange recipient identities as `npub` strings, but the published `p` tag currently expects raw hex. That creates an avoidable mismatch between common operator input and the wire format the plugin needs.

## What Changes

- Accept recipient public keys in Nostr `p` tags as either `npub...` or raw hex.
- Normalize `npub...` values to hex before publishing, so relay output stays compatible with Nostr clients.
- Keep existing tag behavior for all other tag types.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `nostr-notificationforwarder`: published recipient tags MUST accept either `npub` or raw hex public keys and normalize them for relay submission.

## Impact

- Affects `notificationforwarder` Nostr formatter/forwarder behavior.
- Updates the Nostr capability spec to document accepted recipient key formats.
- Adds regression coverage for `npub`-formatted recipient tags.
