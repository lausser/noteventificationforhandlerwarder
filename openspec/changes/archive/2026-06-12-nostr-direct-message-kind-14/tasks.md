## 1. Formatter Update

- [x] 1.1 Audit the current Nostr pipeline and identify the minimum adapter surface needed for `nostr-sdk`.
- [x] 1.2 Replace `pynostr` usage with a `nostr-sdk`-backed publishing path.
- [x] 1.3 Preserve relay and recipient configuration in the new implementation.

## 2. Verification

- [x] 2.1 Add tests for NIP-17 publication behavior and failure handling.
- [x] 2.2 Validate packaging/install assumptions for the new dependency.
- [x] 2.3 Run the targeted notificationforwarder tests for the Nostr path.
