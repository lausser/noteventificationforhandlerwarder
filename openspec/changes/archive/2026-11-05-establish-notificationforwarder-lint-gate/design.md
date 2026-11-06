# Design

## Context

See proposal.md. The baseline command `uvx flake8 src/notificationforwarder/ --max-line-length=120 --statistics --count` reported 119 findings on the committed notificationforwarder source with flake8 7.5.0. Twenty are F821: one undefined `self` in RabbitMQ disconnect and 19 `logger` references in four modules whose globals are injected by `component_loader.load_forwarder()`. The CI lint step is currently an echo placeholder, and the test matrix covers Python 3.9 through 3.14.5. The test extra lists flake8 without a version pin.

## Goals / Non-Goals

**Goals:** Prevent future undefined names without breaking the existing dynamic plugin loader, and make the gate reproducible locally and in CI.

**Non-Goals:** A clean default flake8 run, sweeping formatting and unused-import changes, general RabbitMQ transport coverage, eventhandler linting, or rewriting the archived spool change's unchecked task.

## Decisions

### Focused lint policy

Add `notificationforwarder/.flake8` with `select = E9,E722,F63,F7,F82` and `max-line-length = 120`. This gates structural/syntax errors, bare excepts and undefined names, while leaving existing style and other findings outside the gate. Do not ignore F821 globally, per file, or with inline noqa. Keep a documented explicit full-report command using `--isolated` and `--max-line-length=120` so the focused config does not hide the remaining diagnostics. The other findings are not certified harmless.

### Preserve plugin loading

Initialize `logger = None` in the built-in example, nostr, rabbitmq and webhook forwarder modules; the component loader replaces the global before constructing a loaded plugin. Preserve oauth2 webhook's existing logger synchronization. Direct use before injection can change a NameError into an AttributeError; verify loaded and inherited paths through existing tests. The alternative of suppressing F821 would also hide genuine undefined names.

### Fix the substantive findings

Correct RabbitMQ `disconnect(iself)` to `disconnect(self)`, preserving ordinary close-error handling. Test `close()` is called and an ordinary close exception remains handled using a stubbed pika module and mock connection, without a broker or optional-package requirement. Narrow the JSON traceback formatting `except:` to `except Exception:`; ordinary formatting errors remain handled, whereas KeyboardInterrupt and SystemExit propagate. Test both outcomes.

### Deterministic CI and contributor commands

Use an explicit `--config` pointing to the project-specific flake8 config so discovery is not cwd-dependent. Run the gate once in a Python 3.12 CI job with a compatible pinned flake8 version (7.5.0), while preserving the existing test matrix and test-dependency installation. Document the project-directory and repo-root invocations. Verify the pinned linter actually runs in that CI environment; do not pin it across Python 3.9 and 3.10, which cannot install flake8 7.5.0. Add an isolated lint probe proving that an introduced undefined name makes the gate fail, and that a missing config fails closed.

## Risks / Trade-offs

- [Unselected findings] → They remain visible in the full report; review potentially semantic findings independently rather than treating them as cosmetic.
- [Behavioral changes] → Disconnect now closes the connection; JSON trace formatting no longer swallows control-flow exceptions. Pin both effects with focused tests and rerun the full suite.
- [Version drift] → Pin the dedicated CI gate and document the expected flake8 version; leave the package's existing test matrix intact.
- [False confidence in F821] → Prove the gate rejects an undefined name and avoid suppressions that would hide the RabbitMQ typo.

## Migration Plan

Add configuration and targeted fixes, run focused and full tests, then enable the CI gate. Roll back by reverting the change; no data migration is needed.
