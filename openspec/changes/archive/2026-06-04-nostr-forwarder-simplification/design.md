## Context

The Nostr plugin was built iteratively: first as a public note sender, then as a DM sender, then hardened with compatibility fallbacks to get the behavior working in the current environment. The result is correct, but the forwarder now contains more code than the actual DM flow needs.

We already know the working pynostr pattern: create an `EncryptedDirectMessage`, encrypt it for the recipient, turn it into an event, sign it, and publish it to relays. That gives us a much smaller target shape than the current mixed approach.

## Goals / Non-Goals

**Goals:**
- Keep the Nostr plugin DM-only and easy to reason about.
- Reduce helper and fallback code to the minimum needed for the working path.
- Preserve existing operator-facing behavior and test coverage.
- Keep the message body readable and the recipient `p` tag intact.

**Non-Goals:**
- Reworking the broader notificationforwarder runtime.
- Changing the OpenSpec capability boundary.
- Introducing a new dependency or protocol.
- Adding new delivery modes beyond encrypted DMs.

## Decisions

- Use a single DM publish path based on `EncryptedDirectMessage`.
  - This matches the proven working script and removes the need for separate encryption/event-construction logic.
  - Alternative: keep custom encryption/event assembly in the forwarder. Rejected because it duplicates library behavior and adds complexity.

- Keep recipient resolution near the forwarder boundary.
  - The forwarder should accept configured tags and normalize the `p` recipient tag before publish.
  - Alternative: push all recipient handling into the formatter. Rejected because the forwarder owns transport concerns and should validate DM delivery inputs.

- Preserve the formatter as the place for human-readable alert text.
  - The formatter continues to build the labeled monitoring message.
  - Alternative: collapse formatter and forwarder into one class. Rejected because it breaks the plugin contract and makes the payload less reusable.

- Remove compatibility scaffolding only where it no longer adds value.
  - The simplified forwarder should keep the path understandable, but not retain dead-end branches that exist only for earlier experiments.
  - Alternative: keep all fallback code for safety. Rejected because it makes the code harder to audit and obscures the actual working flow.

## Risks / Trade-offs

- [Less fallback code may reduce resilience in unusual environments] → Keep tests around the DM path and only remove branches that are truly redundant.
- [Over-simplification could accidentally drop tag normalization] → Preserve focused tests for recipient tag handling.
- [A cleaner implementation may change log wording] → Keep log messages stable enough for operators and tests.
- [The simplification might expose hidden assumptions in the existing tests] → Update tests to match the real DM flow rather than the experimental path.
