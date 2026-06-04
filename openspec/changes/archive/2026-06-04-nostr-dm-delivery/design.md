## Context

The existing Nostr forwarder publishes readable public notes to configured relays. That works for feed-style delivery, but it does not surface the alert in chat-oriented clients like FreeFrom, where the user expects the message to appear under `Chats` as a direct message.

This change needs to preserve the current plugin structure while adjusting the Nostr delivery semantics from public note publishing to encrypted DM delivery.

## Goals / Non-Goals

**Goals:**
- Deliver monitoring alerts as encrypted Nostr direct messages.
- Keep the existing formatter/forwarder split and the current plugin loading model.
- Preserve readable monitoring content in the message body.
- Continue to support relay fan-out and secret-safe logging.

**Non-Goals:**
- Reworking the broader notificationforwarder architecture.
- Adding a new UI or mobile app integration.
- Changing eventhandler behavior.
- Introducing a new configuration system.

## Decisions

- Use Nostr DM semantics instead of public note publishing.
  - This aligns with the user's goal of seeing the alert in `Chats`.
  - Alternative: keep public notes and rely on mentions/search. Rejected because it does not satisfy the delivery expectation.

- Keep the formatter as the source of the human-readable monitoring text.
  - The DM body should still be easy to read and include host/service/state/output.
  - Alternative: move all shaping into the forwarder. Rejected because it breaks the existing separation of concerns.

- Preserve recipient identity input as `npub...`.
  - This matches the current operator workflow and avoids forcing raw hex keys.
  - Alternative: require hex-only recipient keys. Rejected because it is less ergonomic and less compatible with existing usage.

- Keep relay publishing and failure handling unchanged where possible.
  - The forwarder should still use the existing retry/spool path for transport failures.
  - Alternative: add a separate DM transport path. Rejected because it would duplicate code.

## Risks / Trade-offs

- [Encryption support may require additional Nostr library capability] → Use the existing library if possible; otherwise isolate the DM-specific logic so it can be swapped without broad changes.
- [Some clients may still surface DMs differently] → Keep the content readable and clearly structured so it is understandable across clients.
- [Changing delivery semantics could affect tests] → Update Nostr tests to verify DM-oriented behavior and keep the public-note path out of the acceptance criteria.
- [Backward compatibility with public notes is lost for this capability] → Scope the change to the Nostr capability only and leave other notification forwarders untouched.
