## Why

The current Nostr implementation works, but it carries extra branching, compatibility shims, and formatter/forwarder indirection that were only needed while we were discovering how to send a DM. Now that the DM path is proven, we can make the plugin smaller, clearer, and easier to maintain.

## What Changes

- Simplify the Nostr forwarder so it follows a single DM-oriented publish path.
- Remove unnecessary fallback logic and compatibility scaffolding from the Nostr plugin.
- Keep the readable monitoring message body and encrypted DM behavior intact.
- Preserve recipient `npub` handling and relay fan-out.
- Keep the plugin contract stable for operators using `notificationforwarder`.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `nostr-notificationforwarder`: simplify the implementation while keeping DM delivery, readable content, and recipient tag handling.

## Impact

- Affects `notificationforwarder/src/notificationforwarder/nostr/forwarder.py` and related tests.
- May reduce or remove fallback-only code paths and helper branches.
- Improves readability and maintainability without changing the operator-facing notification command.
