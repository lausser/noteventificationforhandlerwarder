## 1. Simplify Nostr implementation

- [x] 1.1 Reduce the Nostr forwarder to the minimal DM publish flow using `EncryptedDirectMessage`
- [x] 1.2 Remove redundant compatibility branches and helper code that are no longer needed for the working DM path
- [x] 1.3 Keep recipient `p` tag normalization and relay publication intact

## 2. Validate behavior

- [x] 2.1 Update or trim Nostr tests so they verify the simplified DM flow
- [x] 2.2 Confirm the formatted alert content, recipient handling, and relay publication still work end to end
