## Why

The project's OpenSpec requirements (builtin-plugin-test-coverage, delivery-resilience, developer-experience) mandate comprehensive automated test coverage for the extension points (formatters, forwarders, reporters, deciders, runners, loggers) plus resilience paths and cross-project integration. The loading mechanism treats shipped ("builtin") modules and user-written modules placed in local/lib identically; there is no special path for either. However, the current test corpus is historically accreted and mixed, and the MORE-TESTS-GROK.md inventory shows ~80 must-have cases still unchecked (email, syslog, telegram, default/omd deciders, ssh/nsc runners, baseclass edge cases, heartbeat/probe/spool/enrichment/formatter-failure behaviors, etc.). This leaves critical production paths without direct, comprehensible tests and makes it hard for contributors or agents to understand "how to test an integration the right way."

The goal of this change is not only to close the coverage gaps but to establish an **expert-level test setup**: a flat, layer-based naming convention that makes the runtime architecture visible at a glance, uniform treatment of shipped vs. own modules, preservation of all existing test *functionality* (even if names and locations move), and a small set of tiny, heavily-commented "own module" contract smoke tests that serve as copyable templates for an AI agent or human when told "implement a formatter/forwarder/decider/runner for my external system."

## What Changes

- Reorganize the test corpus (while preserving every exercised code path and assertion) into a flat structure with consistent layer-derived naming across the two sibling subprojects.
- Add all must-have and high-value should-have cases from MORE-TESTS-GROK.md (after rabbitmq exclusion) into the appropriate layer-named files.
- Add a small set of pristine, agent-oriented "own module" contract smoke tests (more than 6 allowed) that demonstrate the uniform extension contract using the same `new()` / handle() paths and pythonpath fixtures that real user modules use.
- Cover the builtin naemonlog reporter (the only reporter that needs dedicated attention, as reporters are optional and rare). Preserve existing custom-reporter logic (e.g. ticketsystem precedence) without expanding "own reporter" smokes.
- Cover success, failure, exception, spool, heartbeat, probe, enrichment, formatting, and cross-project handoff paths using mocks for optional transports (smtplib, SysLogHandler, requests, etc.).
- Fix latent defects discovered during test writing (e.g., telegram `hat_id`/`request_parms`, DecidedEvent missing `_is_heartbeat`, baseclass timeout exception type) as part of making tests pass.
- No changes to runtime behavior or public APIs unless required to make tested behavior match documented intent. RabbitMQ is intentionally out of scope (legacy carry-over with no relevance; no pika tests or server simulation will be added).

## Capabilities

### New Capabilities

(none - this change fulfills requirements already captured in existing specs)

### Modified Capabilities

- `builtin-plugin-test-coverage`: Expand explicit test scenarios to match the full matrix of extension points (formatters, forwarders, reporters on nf only, deciders, runners, loggers), with uniform treatment of shipped and user-provided modules via the same loading mechanism.
- `delivery-resilience`: Add tests for probe-gated flush, heartbeat no-spool, spool replay batch limits, enrichment stripping, and formatter failure paths.
- `developer-experience`: Ensure contributor-facing (and agent-facing) tests cover all documented extension contracts in a clear, copyable way, plus runtime guarantees around loading, fallback, resilience, and cross-project handoff. The test structure itself becomes part of the documentation.

## Impact

- notificationforwarder/tests/ and eventhandler/tests/: flat set of layer-prefixed files (test_loading_resolution.py, test_runtime_*.py, test_orchestration_*.py, test_resilience_*.py, test_contracts_*.py, test_loggers.py, test_integration_*.py, etc.). Existing deep files (test_webhook.py, test_oauth2webhook.py, test_nostr.py, test_delivery_resilience.py, test_reporter.py, etc.) remain for preservation of their logic; their valuable assertions are also expressed in the layer files where appropriate.
- A small number of new tiny `test_contracts_own_*_smoke.py` (or sections inside the contracts files) that are deliberately minimal, uniform, and heavily commented as agent templates.
- `test_contracts_reporters.py` exists only on the notificationforwarder side (builtin naemonlog focus + preserved custom logic). No reporter file or dummy tests on the eventhandler side.
- Potential minimal source patches in forwarders/runners/deciders if tests expose copy-paste errors or untested control flows.
- Test dependencies remain the same (pytest, monkeypatch); optional deps skipped via pytest.importorskip.
- Improves confidence for future changes and makes the test suite itself a clear map of the runtime architecture; no user-facing or breaking changes.
