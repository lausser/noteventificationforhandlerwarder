## ADDED Requirements

### Requirement: Nostr relay publishing
The `notificationforwarder` system MUST be able to publish a formatted monitoring notification as a signed Nostr text note to one or more configured relays.

#### Scenario: Publish to configured relays
- **WHEN** a Nostr forwarder is configured with relay URLs and a signing key
- **THEN** the system MUST publish the notification to each configured relay

#### Scenario: Relay publish failure
- **WHEN** a relay cannot accept or deliver the published event
- **THEN** the forwarder MUST report the failure so the existing retry path can handle it

### Requirement: Nostr event shaping
The `notificationforwarder` system MUST provide a formatter that maps monitoring event fields into Nostr note content and optional tags.

#### Scenario: Format monitoring event
- **WHEN** a monitoring event is passed to the Nostr formatter
- **THEN** the formatter MUST produce a markdown-like note body with labeled lines for `Host:`, `Service:`, `State:`, and `Output:`

#### Scenario: Preserve event context
- **WHEN** the source event contains host, service, state, or output fields
- **THEN** the formatter MUST include the relevant context in the generated Nostr content or tags

#### Scenario: Structured note body is readable in clients
- **WHEN** a user opens the published Nostr note in a standard client
- **THEN** the note body MUST remain readable without requiring custom rendering or a template engine

### Requirement: Secure key handling
The `notificationforwarder` system MUST support configuring the Nostr signing key without exposing it in normal logs.

#### Scenario: Key configured for publishing
- **WHEN** a private key or secret reference is provided in forwarder options
- **THEN** the system MUST use it for signing and MUST NOT print the secret value in logs

### Requirement: Formatter includes keypair guidance
The Nostr formatter source file MUST include a header comment with a small `pynostr`-based Python script that shows how to create a keypair and derive the `nsec` and `npub` values.

#### Scenario: Contributor opens the formatter module
- **WHEN** a contributor reads `nostr/formatter.py`
- **THEN** the file MUST contain a header comment that explains how to generate the keypair and the corresponding `nsec` and `npub`

### Requirement: Default monitoring tag
The `notificationforwarder` system MUST include a `monitoring` tag and event-specific tags for host, service, and state on published Nostr notes unless the formatter or forwarder configuration explicitly overrides them.

#### Scenario: Publish a default-tagged note
- **WHEN** the Nostr forwarder publishes a note using the default configuration
- **THEN** the note MUST include the `monitoring` tag and tags derived from host, service, and state when those values are present
