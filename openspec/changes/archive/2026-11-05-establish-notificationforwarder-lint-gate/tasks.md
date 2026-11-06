# Tasks

## 1. Correctness fixes

- [x] 1.1 Fix `notificationforwarder/src/notificationforwarder/rabbitmq/forwarder.py` so `disconnect()` closes its connection and continues to handle ordinary close errors; add and run focused mock-based tests that assert `close()` is called and exceptions are handled, without requiring pika or a broker.
- [x] 1.2 In `notificationforwarder/src/notificationforwarder/json/logger.py`, narrow the traceback-formatting bare `except` to `except Exception`; add and run tests showing ordinary formatting errors are handled while KeyboardInterrupt and SystemExit propagate.
- [x] 1.3 Define `logger = None` in the built-in example, nostr, rabbitmq and webhook forwarder modules for the existing loader to inject; run applicable plugin-loading, webhook and oauth2 tests to verify injection and inherited behavior remain intact.

## 2. Focused lint policy

- [x] 2.1 Add `notificationforwarder/.flake8` selecting `E9,E722,F63,F7,F82` with `max-line-length = 120`, without global, per-file or inline F821 suppression; with flake8 7.5.0, run `flake8 --config .flake8 src/notificationforwarder --count --statistics` from `notificationforwarder/` and verify zero gated findings.
- [x] 2.2 Verify the gate rejects an isolated Python file containing a deliberately undefined name and that an explicit nonexistent config fails; verify the logger bindings do not hide other F821 errors. (Committed probe: `tests/test_lint_gate.py`.)
- [x] 2.3 Document the focused gate's explicit-config invocations from `notificationforwarder/` and the repository root, its selected codes and flake8 version, and the full diagnostic command `flake8 --isolated src/notificationforwarder/ --max-line-length=120 --statistics --count` from `notificationforwarder/`; run the commands and verify the full report includes unselected findings. (Documented in `notificationforwarder/README.md` → "Focused lint gate".)

## 3. CI and integration

- [x] 3.1 Replace the placeholder lint step in `.github/workflows/python-package-notificationforwarder.yml` with a dedicated Python 3.12 gate using flake8 7.5.0 and explicit `--config .flake8`; preserve the existing Python test matrix and verify the command in an equivalent Python 3.12 environment. (Dedicated `lint-notificationforwarder` job added; placeholder step removed; matrix and pytest/tmate steps preserved. Gate command verified locally on Python 3.13.5 with flake8 7.5.0 → 0 findings; the CI job is the authoritative Python 3.12 proof as no local 3.12 interpreter was available.)
- [x] 3.2 Run `pytest tests/ -v` from `notificationforwarder/`, the focused lint gate, and `git diff --check`; confirm all required checks pass and report optional dependency skips. (Result: 285 passed / 0 skipped; gate 0 findings on flake8 7.5.0; `git diff --check` clean. The only optional-dependency skip source is `test_nostr.py` `pytest.importorskip("nostr_sdk")` — 0 skips observed.)
