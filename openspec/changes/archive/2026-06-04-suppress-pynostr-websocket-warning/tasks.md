## 1. Investigate and isolate the warning

- [x] 1.1 Reproduce the `websocket_ping_timeout` warning in the Nostr forwarder startup path.
- [x] 1.2 Identify the exact `pynostr` call or configuration that emits the warning.
- [x] 1.3 Decide whether the smallest fix is a parameter change or local output suppression.

## 2. Implement the quiet startup path

- [x] 2.1 Apply the minimal code change to prevent the warning from appearing during normal startup.
- [x] 2.2 Keep dependency failure behavior unchanged for missing `pynostr`.
- [x] 2.3 Ensure relay publishing still uses the same runtime flow after initialization.

## 3. Add regression coverage

- [x] 3.1 Add a test that confirms the warning is no longer emitted on the normal path.
- [x] 3.2 Add or update a test to confirm the forwarder still initializes successfully.
- [x] 3.3 Verify the existing Nostr failure path still reports missing dependency errors.
