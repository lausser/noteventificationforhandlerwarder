## Why

Monitoring users need a simple way to publish alerts to Nostr without adding a separate integration stack. This change adds a lightweight Nostr notification path to `notificationforwarder` so alerts can be relayed to Nostr relays with minimal new surface area.

## What Changes

- Add a Nostr formatter that turns monitoring events into readable note content and tags.
- Add a Nostr forwarder that signs and publishes events to configured relays.
- Use `pynostr` for key handling, signing, and relay publishing.
- Keep the feature small, backward-compatible, and isolated to the `notificationforwarder` plugin model.

## Capabilities

### New Capabilities
- `nostr-notificationforwarder`: send monitoring notifications to Nostr relays from `notificationforwarder` using `pynostr`.

### Modified Capabilities
- 

## Impact

- Affects `notificationforwarder` plugin discovery and delivery flow.
- Adds the `pynostr` Python dependency for Nostr event signing/publishing.
- Introduces new forwarder options for relay URLs, `nsec` keys, and event metadata mapping.
- No expected changes to `eventhandler`.
