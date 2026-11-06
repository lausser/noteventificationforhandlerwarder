## Context

The repository contains two Python subprojects (notificationforwarder and eventhandler) that rely on a plugin architecture for formatters, forwarders, reporters (nf only), deciders, runners, and loggers. The component loading mechanism (`resolve_component` + `load_*` / `load_component`) is deliberately uniform: shipped modules under `src/...` and user-written modules placed in `local/lib/python/...` (or `lib/python/...`) are resolved and instantiated through exactly the same code paths. There is no special "builtin" branch.

OpenSpec specs (builtin-plugin-test-coverage, delivery-resilience, developer-experience) require that the extension points have direct automated tests covering normal behavior, important failure/edge cases, spool/retry semantics, heartbeat handling, probe gating, enrichment, formatting failures, and cross-subproject handoff.

An audit captured in MORE-TESTS-GROK.md (506 lines) enumerated ~237 specific test cases across must-have / should-have / nice-to-have priority. At the time of this change, the corpus is historically accreted and mixed (especially `test_builtin_plugins_focus.py` on both sides, `test_reporter.py`, the unittest-style logger files, and the example `test_classes.py` files). Large areas (email, syslog, telegram, default/omd deciders, ssh/nsc_web runners, baseclass edge cases, resilience edges) have little or no direct coverage, and the structure itself does not make the runtime layers obvious.

The intent of this change is to close the coverage gaps **while establishing an expert-level test setup**:
- A flat structure with consistent layer-derived naming across the two sibling subprojects (loading_resolution, runtime_*, orchestration_*, resilience_*, contracts_*, loggers, integration_*).
- Uniform demonstration that shipped and own modules are tested the same way.
- Preservation of all existing test *functionality* (the code paths and assertions that are exercised today must continue to be exercised; individual test names and file locations may change).
- A small set of tiny, heavily-commented "own module" contract smoke tests (more than 6 allowed) that serve as copyable templates for contributors or AI agents when asked to implement a new external integration.
- Reporter coverage scoped to the builtin naemonlog reporter (reporters are optional and rare); existing custom-reporter logic is preserved but no new "own reporter" smokes are required. No reporter file or dummy tests on the eventhandler side.

Existing patterns (`_new_forwarder` / `_formatted_event` / `_new_runner` helpers, OMD_ROOT fixtures, monkeypatch style in `test_delivery_resilience.py` and `test_builtin_plugins_focus.py`, pythonpath test modules, server_fixture integration) provide the foundation. RabbitMQ is intentionally out of scope (legacy carry-over with no relevance; no pika-based tests or server simulation will be added).

## Goals / Non-Goals

**Goals:**
- Close all must-have gaps from MORE-TESTS-GROK.md (after rabbitmq exclusion) plus high-value should-haves, using the exact scenarios listed.
- Establish a clear, expert-level test organization: flat structure with consistent layer-derived naming across the two sibling subprojects (test_loading_resolution.py, test_runtime_*.py, test_orchestration_*.py, test_resilience_*.py, test_contracts_formatters.py / forwarders.py / reporters.py (nf only) / deciders.py / runners.py, test_loggers.py, test_integration_cross.py, etc.).
- Make the test suite itself a visible map of the runtime architecture (loading → runtime/bootstrap → orchestration/flow → resilience → contracts per extension point → loggers → integration).
- Demonstrate and enforce uniform treatment: shipped modules and user-written "own modules" (local/lib) are loaded and exercised through identical paths; tests for one are valid templates for the other.
- Add a small set of tiny, heavily-commented "own module" contract smoke tests (more than 6 is acceptable) that are deliberately suitable as copy-paste templates for an AI agent or human when told "I need a formatter/forwarder/decider/runner for Ticket System XY — here is the API/payload".
- Preserve all existing test *functionality*: every code path, contract surface, edge, and integration scenario that is currently exercised must continue to be exercised. Individual test function names and file locations may change or move.
- Scope reporter coverage to the builtin naemonlog reporter (reporters are optional and rare). Preserve existing custom-reporter logic (e.g. ticketsystem report_payload precedence) without creating new "own reporter" smokes or any reporter files/tests on the eventhandler side.
- Use test writing to surface and correct copy-paste defects (telegram typos, DecidedEvent missing _is_heartbeat, baseclass timeout exception type, etc.).
- Keep the entire suite runnable in minimal CI: pytest.importorskip for pynostr, mocks for smtplib/SysLogHandler/requests, no real external services required.

**Non-Goals:**
- Do not introduce new runtime features, public APIs, or behavioral changes except where a test demonstrates that current code deviates from documented intent.
- Do not create empty or placeholder files on either side for concepts that do not exist in that subproject (no test_contracts_reporters.py on eventhandler, no rabbitmq tests anywhere in this change).
- Do not reorganize the test suite in a way that loses coverage of currently exercised paths.
- Do not add performance, load, or long-running concurrency tests unless they fall out naturally from must-have scenarios.
- Do not require optional third-party services (real SMTP, RabbitMQ, Telegram relays, etc.).
- Do not modify master spec files under openspec/specs/ (only delta specs under this change).

## Decisions

- **Testing strategy**: Prefer focused unit tests with monkeypatch for new coverage (email submit paths, syslog, telegram, probe/heartbeat/spool edges, decider branches, runner command rendering, baseclass paths, etc.). Retain and preserve the existing heavy integration-style tests (webhook/oauth2 with server_fixture, cross-project notify runs, custom pythonpath module end-to-end runs) exactly because they exercise the full user-visible story. The new tiny agent smokes are deliberately small and uniform; the deep files keep doing the valuable heavy lifting.

- **File organization (expert-level flat structure)**: A flat `tests/` per subproject with consistent layer-derived naming that makes the runtime architecture visible at directory-listing time. Siblings use the same prefix style; they are not required to mirror contents.

  Notificationforwarder example:
  - test_loading_resolution.py
  - test_runtime_config_paths.py
  - test_orchestration_flow.py
  - test_resilience_spool.py
  - test_contracts_formatters.py
  - test_contracts_forwarders.py
  - test_contracts_reporters.py (builtin naemonlog focus + preserved custom logic; no equivalent on eh side)
  - test_loggers.py
  - test_integration_cli.py
  - test_integration_cross.py

  Eventhandler example (same prefixes, only the layers that exist):
  - test_loading_resolution.py
  - test_runtime_bootstrap.py
  - test_orchestration_handle.py
  - test_resilience_concurrency.py
  - test_contracts_deciders.py
  - test_contracts_runners.py
  - test_loggers.py
  - test_integration_cli.py
  - test_integration_cross.py

  Existing deep files (test_webhook.py, test_oauth2webhook.py, test_nostr.py, test_delivery_resilience.py, test_reporter.py, test_builtin_plugins_focus.py, test_classes.py, the unittest logger files, test_notify.py, etc.) remain in place for preservation. Their valuable logic and assertions may also be expressed (or re-expressed) inside the layer-named files. No existing test *functionality* is deleted.

  The two `pythonpath/` trees under `tests/` are first-class fixtures that prove the uniform extension model; the new agent smokes load from them (or from tiny dedicated smoke-only modules) using the exact same `new()` / handle() entry points that real user code would use.

- **Own-module contract smokes (agent templates)**: A small set (more than 6 allowed) of deliberately tiny, heavily-commented tests whose only job is to be the thing an agent or human copies when told "I need to send notifications to Ticket System XY, here is the API and payload description." They exercise the uniform contract surface (payload+summary for formatters, submit/forward/heartbeat/spool semantics for forwarders, decide_and_prepare + discard for deciders, run() outcomes + payload override for runners, cross-handoff event shape) using `new()` + pythonpath overrides. One of them is the cross-handoff smoke that deliberately ties the two siblings together. Reporters are intentionally *not* given their own smoke in this minimal set (builtin naemonlog coverage + preservation of existing custom logic is sufficient).

- **Preservation definition (per clarified requirements)**: The test *functionality* and the code paths it exercises must survive. Individual `def test_*` names may change. Tests may move between files. The invariant is that every currently exercised contract, edge, resilience path, loading rule, enrichment behavior, cross-project handoff, logger message branch, reporter line, etc. continues to have an active, running assertion after the change.

- **Mocking boundaries and assertions**: Mock at the real transport boundary used by the module (smtplib.SMTP, SysLogHandler, requests, etc.). Reuse spool patterns from test_delivery_resilience.py (num_spooled_events, direct sqlite for expiry/replay edges, log substring checks, signature-file side effects). For heartbeat vs non-heartbeat, probe gating, and reporter precedence, assert both the return value / side effect and the observable log or spool state.

- **Defect handling**: When a test written against documented behavior fails because of a clear copy-paste or control-flow bug (telegram typos, DecidedEvent `_is_heartbeat`, baseclass timeout exception type, etc.), include the minimal source fix in the same change so the test can pass. Record it in the commit message. Do not expand scope beyond making the intended behavior testable and correct. RabbitMQ-related defects are out of scope.

- **Optional dependency handling**: pytest.importorskip("pynostr") for all nostr tests. SSH runner tests may mock resolve_identity_file. No pika anywhere in this change.

- **Order of implementation**: Must-haves first (email/syslog/telegram transport, runtime resilience edges, eventhandler decider/runner/baseclass boundaries, nostr gaps, cross-project), then should-haves, then the tiny agent smokes as the final "this is how you test your own module" layer. Verification runs the full suites of both subprojects.

- **No new test dependencies**: pytest + stdlib (SimpleNamespace, monkeypatch) + the project's own modules and pythonpath fixtures.

## Test Quality Notes

Not all tests have equal bug-catching value. The following categories are acknowledged:

- **High-value tests** (exercise real complexity, likely to catch bugs): flush() replay edge cases including formatter-failure-during-replay and stuck detection; webhook header merging from 3 sources with case-insensitive Content-Type check; webhook URL mutation side effect; oauth2 token lifecycle (cache, refresh, network errors, malformed responses); nostr async behavior; SpoolStore direct tests (concurrent access, boundary conditions, malformed data); logger branch coverage (~30 distinct message patterns in TextLogger._build_message); cross-project integration paths.

- **Defect-exposing tests** (will fail initially, pass after fix): email forwarder logging.critical vs logger.critical (email/forwarder.py:34); telegram hat_id/request_parms typos + missing logger import (telegram/forwarder.py:9,36,38); eventhandler timeout decorator ForwarderTimeoutError vs RunnerTimeoutError (eventhandler/baseclass.py:144,156); SshRunner missing resolve_identity_file import (ssh/runner.py:10). These tests are written to assert the *correct* behavior so they fail before the fix and pass after.

- **Pedagogical tests** (documentation disguised as tests, low bug-catching value but high onboarding value): own-module contract smokes (§9). These exercise the pythonpath loading mechanism (which is real functionality) but their primary purpose is to serve as copyable templates for agents and contributors implementing new integrations.

- **Completeness tests** (test trivial logic, kept for coverage completeness): syslog facility/priority normalization (simple string-to-constant mapping), decider boundary tests for simple branching logic. These verify that lookup tables and straightforward conditionals work correctly.

The implementation order prioritizes high-value and defect-exposing tests (must-haves §4–§7) before pedagogical and completeness tests (should-haves §8, smokes §9).

## Risks / Trade-offs

- [Large test surface + reorganization] → Mitigate by treating preservation as "functionality and coverage must survive," not "original names and locations must be byte-identical." Use the task list to track both new cases and "move/re-express existing logic into layer file X while keeping the assertions." Partial delivery (e.g., must-haves + structure) still provides massive value.
- [Test writing may expose additional latent defects] → Accept controlled source changes; keep edits minimal and focused on making documented behavior match reality. Each such fix is a win for reliability.
- [Maintaining tests for modules with known runtime bugs (telegram)] → The tests will document the current broken surface; fixes can be made in the same change or a follow-up. This is preferable to leaving the surface untested.
- [CI environments lacking optional packages] → importorskip + mocks ensure the suite remains green everywhere; the skipped tests still serve as documentation of what should be exercised when the deps are present.
- [Over-testing implementation details] → Focus assertions on observable outcomes (return values, log messages, spool contents, side-effect files, payload shapes passed to external clients, report lines, cross-handoff event shape) rather than private method calls.
- [Asymmetry between siblings (no reporters on eh)] → This is accurate and intentional. The flat naming style is consistent; the contents differ where the systems differ. No empty files or dummy tests will be created.
- [Agent smokes could be over- or under-weighted] → Size the set to what actually helps an agent (formatters, forwarders, deciders, runners, cross-handoff). Reporter is deliberately kept out of the minimal smoke set per scoping. The combined "full target" smoke on nf is allowed and valuable.
