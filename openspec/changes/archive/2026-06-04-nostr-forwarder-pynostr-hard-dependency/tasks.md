## 1. Simplify Nostr dependency handling

- [x] 1.1 Remove the local fallback stand-ins from the Nostr forwarder module.
- [x] 1.2 Keep import-time failure as the only behavior when `pynostr` is missing.
- [x] 1.3 Preserve the existing baseclass error path for logging and aborting.

## 2. Verify behavior

- [x] 2.1 Update tests to assert that missing `pynostr` raises immediately.
- [x] 2.2 Update or retain tests that cover the normal publish path with the real library.
- [x] 2.3 Run the Nostr test coverage and confirm the simplified dependency path behaves as expected.
