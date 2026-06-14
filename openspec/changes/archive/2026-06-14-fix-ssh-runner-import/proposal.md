## Why

`eventhandler/src/eventhandler/ssh/runner.py` references `resolve_identity_file()` without importing it from `eventhandler.baseclass`. This causes a `NameError` at runtime whenever a user configures `identity_file` via runner options. The bug has gone undetected because no test exercises the SSH runner with an identity file configured.

## What Changes

- Add the missing `from eventhandler.baseclass import resolve_identity_file` import to `ssh/runner.py`.
- Add a test that instantiates `SshRunner` with `identity_file` set and verifies the resolved path.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

_(none — this is a bug fix, not a spec-level behavior change)_

## Impact

- **Code**: `eventhandler/src/eventhandler/ssh/runner.py` (1-line import addition)
- **Tests**: `eventhandler/tests/test_contracts_runners.py` or `test_builtin_plugins_focus.py` (new test case)
- **Dependencies**: none
- **Breaking changes**: none
