## Purpose

Deliver monitoring notifications as encrypted Nostr direct messages so they arrive in chat-oriented clients while preserving readable alert content and the existing notificationforwarder runtime model.

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
