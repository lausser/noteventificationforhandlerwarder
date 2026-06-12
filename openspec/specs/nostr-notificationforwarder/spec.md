## Purpose

Deliver monitoring notifications as encrypted Nostr direct messages using the `nostr-sdk` library, supporting both NIP-04 and NIP-17 protocols.

## Requirements

### Requirement: Nostr relay publishing
The `notificationforwarder` system MUST be able to publish a formatted monitoring notification as an encrypted Nostr direct message to a configured recipient through one or more configured relays.

#### Scenario: Publish direct message to recipient
- **WHEN** a Nostr forwarder is configured with relay URLs, a signing key, and a recipient public key
- **THEN** the system MUST encrypt the notification for that recipient and publish it to each configured relay
- **AND** the resulting message MUST be readable by the recipient in a DM/chat view

#### Scenario: Relay publish failure
- **WHEN** a relay cannot accept or deliver the published event
- **THEN** the forwarder MUST report the failure so the existing retry path can handle it

### Requirement: Quiet Nostr websocket startup
The `notificationforwarder` system MUST avoid emitting the known `websocket_ping_timeout` warning during normal Nostr forwarder initialization.

#### Scenario: Default Nostr startup does not warn
- **WHEN** the Nostr forwarder starts with its standard websocket configuration
- **THEN** the runtime MUST not print the `websocket_ping_timeout` warning to the console or logs
- **AND** Nostr publishing MUST continue to work normally

#### Scenario: Warning suppression does not change delivery behavior
- **WHEN** the forwarder initializes a relay connection after applying the quiet startup behavior
- **THEN** the relay connection MUST still be usable for publishing notifications
- **AND** the system MUST preserve the existing fail-fast behavior for missing `nostr-sdk`

### Requirement: Nostr event shaping
The `notificationforwarder` system MUST provide a formatter that maps monitoring event fields into Nostr message content and recipient tags for direct message delivery.

#### Scenario: Format monitoring event
- **WHEN** a monitoring event is passed to the Nostr formatter
- **THEN** the formatter MUST produce a readable message body with labeled lines for `Host:`, `Service:`, `State:`, and `Output:`

#### Scenario: Preserve event context
- **WHEN** the source event contains host, service, state, or output fields
- **THEN** the formatter MUST include the relevant context in the generated Nostr message body or recipient tags

#### Scenario: Structured message body is readable in clients
- **WHEN** a user opens the published Nostr message in a standard client
- **THEN** the message body MUST remain readable without requiring custom rendering or a template engine

### Requirement: Secure key handling
The `notificationforwarder` system MUST support configuring the Nostr signing key without exposing it in normal logs.

#### Scenario: Key configured for publishing
- **WHEN** a private key or secret reference is provided in forwarder options
- **THEN** the system MUST use it for signing and MUST NOT print the secret value in logs

### Requirement: Default monitoring tag
The `notificationforwarder` system MUST include a `monitoring` tag and event-specific tags for host, service, and state on published Nostr messages unless the formatter or forwarder configuration explicitly overrides them.

#### Scenario: Publish a default-tagged message
- **WHEN** the Nostr forwarder publishes a message using the default configuration
- **THEN** the message MUST include the `monitoring` tag and tags derived from host, service, and state when those values are present

### Requirement: Nostr dependency failure behavior
The `notificationforwarder` system MUST fail fast when the `nostr-sdk` dependency is unavailable instead of substituting local fallback implementations.

#### Scenario: Import dependency is missing
- **WHEN** the Nostr forwarder module is loaded and `nostr-sdk` cannot be imported
- **THEN** the import MUST raise an exception and the baseclass error handling MUST report the failure
- **AND** the module MUST NOT create local stand-in classes for `Client`, `Keys`, `NostrSigner`, `PublicKey`, or `RelayUrl`

### Requirement: Support both NIP-04 and NIP-17 Nostr protocols
The Nostr forwarder MUST support publishing encrypted direct messages using either NIP-04 (standard encrypted DM) or NIP-17 (private DM) protocols based on configuration.

#### Scenario: NIP-04 mode configuration
- **WHEN** the forwarder is configured with `nip_mode=nip04` (or no mode specified)
- **THEN** the system MUST publish messages using the NIP-04 protocol via the `nostr-sdk` library
- **AND** messages MUST be published to configured relays with encryption for the recipient

#### Scenario: NIP-17 mode configuration
- **WHEN** the forwarder is configured with `nip_mode=nip17`
- **THEN** the system MUST publish messages using the NIP-17 private DM protocol via the `nostr-sdk` library
- **AND** messages MUST be wrapped using NIP-59 Gift Wrap semantics

#### Scenario: NIP mode selection is logged
- **WHEN** the forwarder initializes a publishing operation
- **THEN** a DEBUG log entry MUST indicate which NIP mode is being used

#### Scenario: Formatter output is protocol-agnostic
- **WHEN** the Nostr formatter processes an event
- **THEN** it MUST produce a payload with content and tags without hardcoding protocol-specific event kind
- **AND** the forwarder MUST determine the final protocol based on configuration
