## 1. Nostr DM delivery

- [x] 1.1 Update the Nostr forwarder to publish encrypted direct messages instead of public notes
- [x] 1.2 Adjust message construction so the readable monitoring content is preserved in the DM body
- [x] 1.3 Keep recipient `npub` handling and relay fan-out working with the DM path

## 2. Verification

- [x] 2.1 Add or update tests to cover DM-oriented publishing behavior
- [x] 2.2 Add or update tests to verify the user-visible content still includes host, service, state, and output
- [x] 2.3 Run the relevant Nostr test coverage and confirm the change is ready for implementation
