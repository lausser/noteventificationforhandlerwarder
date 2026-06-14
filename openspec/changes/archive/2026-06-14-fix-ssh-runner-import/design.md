## Context

`eventhandler/src/eventhandler/ssh/runner.py` calls `resolve_identity_file()` at line 10 without importing it. The function is defined in `eventhandler.baseclass` and used to expand `~` and resolve the identity file path to an absolute path.

The bug has gone undetected because no test exercises `SshRunner` with an `identity_file` configured. The existing `test_ssh_runner_import_is_not_covered_due_to_missing_dependency` test confirms that the SSH runner can be imported but doesn't test the `__init__` path with an identity file.

## Goals / Non-Goals

**Goals:**
- Fix the missing import so `SshRunner` works with `identity_file` configured.
- Add a test that verifies the identity file path is resolved.

**Non-Goals:**
- Refactoring the SSH runner to use a different identity file resolution strategy.
- Adding SSH connectivity tests (those belong in integration tests).

## Decisions

**Add the import inline with the existing import line.**

The current import is `from eventhandler.baseclass import EventhandlerRunner`. Adding `resolve_identity_file` to this import is the minimal, idiomatic fix. No new module or reorganization needed.

## Risks / Trade-offs

**Risk:** None — this is a straightforward missing import fix.
