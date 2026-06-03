## 1. Dependency and API validation

- [x] 1.1 Add `pynostr` as the Nostr dependency and confirm the integration path
- [x] 1.2 Decide the minimal relay/key configuration surface for the plugin

## 2. Formatter implementation

- [x] 2.1 Add a Nostr formatter that maps monitoring fields into note content and tags
- [x] 2.2 Add tests that verify the markdown-like note body, host/service/state/output labels, and default tags
- [x] 2.3 Add a header comment in `nostr/formatter.py` showing `pynostr` keypair generation and `nsec`/`npub` derivation

## 3. Forwarder implementation

- [x] 3.1 Add a Nostr forwarder that signs and publishes events to configured relays
- [x] 3.2 Wire failure handling into the existing retry/spool behavior
- [x] 3.3 Add tests for successful publish, relay failure, and secret-safe logging

## 4. Documentation and verification

- [x] 4.1 Document the new Nostr formatter and forwarder options
- [x] 4.2 Run the relevant test suite and fix any regressions
