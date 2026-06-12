## ADDED Requirements

### Requirement: Nostr private messages use NIP-17 support
The Nostr notificationforwarder SHALL publish private direct messages through a library-backed NIP-17 implementation rather than by manually constructing NIP-04 direct-message events.

#### Scenario: Publish private message
- **WHEN** notificationforwarder sends a Nostr direct message
- **THEN** it SHALL use a NIP-17-capable publishing API

#### Scenario: No manual NIP-04 event assembly
- **WHEN** notificationforwarder prepares a Nostr direct message
- **THEN** it SHALL NOT depend on constructing a kind 4 encrypted DM event manually
