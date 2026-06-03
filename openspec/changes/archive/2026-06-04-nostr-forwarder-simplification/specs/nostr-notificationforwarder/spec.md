## ADDED Requirements

### Requirement: Nostr DM publish flow is minimal
The `notificationforwarder` system MUST publish Nostr notifications through a single direct-message flow that encrypts the formatted content for the configured recipient and sends the resulting event to the configured relays.

#### Scenario: Publish a direct message
- **WHEN** the Nostr forwarder is configured with relay URLs, a signing key, and a recipient `p` tag
- **THEN** the system MUST encrypt the formatted content as a direct message and publish it to each configured relay

### Requirement: Nostr message formatting remains readable
The `notificationforwarder` system MUST keep the Nostr message body as a plain, labeled monitoring summary that is readable in standard DM/chat clients.

#### Scenario: Format monitoring event
- **WHEN** a monitoring event is passed to the Nostr formatter
- **THEN** the formatter MUST produce labeled lines for `Host:`, `Service:`, `State:`, and `Output:`

### Requirement: Nostr recipient handling is preserved
The `notificationforwarder` system MUST preserve recipient `npub` handling and tag normalization so operators can configure the DM recipient using familiar Nostr key formats.

#### Scenario: Normalize recipient key
- **WHEN** the configured recipient tag uses an `npub1...` value
- **THEN** the system MUST normalize it for DM publication without changing the operator-facing configuration format

### Requirement: Nostr logging remains operationally useful
The `notificationforwarder` system MUST continue to log successful and failed Nostr DM delivery attempts without exposing secret key material.

#### Scenario: DM publish succeeds or fails
- **WHEN** the forwarder sends or attempts to send a Nostr DM
- **THEN** the runtime MUST record the delivery outcome in the log and MUST NOT print the private key value
