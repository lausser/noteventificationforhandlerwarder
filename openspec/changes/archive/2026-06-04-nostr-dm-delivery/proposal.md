## Why

Operators using Nostr need monitoring alerts to arrive as direct messages, not public notes, so they show up in chat-style clients like FreeFrom. The current Nostr delivery path publishes readable public notes, which makes the alert easy to miss in `Chats`.

## What Changes

- Update the Nostr delivery path to publish encrypted direct messages to a configured recipient.
- Preserve the existing readable monitoring content inside the DM body so the alert still carries host, service, state, and output context.
- Keep relay publishing and signing behavior intact.
- Continue to accept recipient identifiers in the common `npub...` form.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `nostr-notificationforwarder`: send monitoring notifications as encrypted Nostr direct messages to a configured recipient instead of public notes.

## Impact

- Affects the `notificationforwarder` Nostr formatter and forwarder behavior.
- Requires message shaping changes so the payload can be published as a DM.
- May require additional Nostr library support for encrypted DM publishing.
- Improves compatibility with chat-based Nostr clients.
