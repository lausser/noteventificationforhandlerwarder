# eventhandler Test Suite

This document describes every test file, test case, and the code paths they cover.

**Audience:** Engineers reading these tests to understand *what* is being verified and *why* — not just what the assertion says.

**Conventions:**
- All tests require `OMD_ROOT` to be set; fixtures handle this automatically.
- `monkeypatch` is used to intercept subprocess calls, deciders, runners, and forwarders.
- `DecidedEvent` instances are created via dicts passed to `_decided_event()`.
- `CapturingForwarder` is a test helper that captures forwarded events for assertion.

---

## Table of Contents

- [test_package.py](#test_packagepy)
- [test_classes.py](#test_classespy)
- [test_builtin_plugins_focus.py](#test_builtin_plugins_focuspy)
- [test_loggers.py](#test_loggerspy)
- [test_contracts_deciders.py](#test_contracts_deciderspy)
- [test_contracts_runners.py](#test_contracts_runnerspy)
- [test_orchestration_handle.py](#test_orchestration_handlepy)
- [test_integration_cross.py](#test_integration_crosspy)
- [test_notify.py](#test_notifypy)
- [test_logger.py](#test_loggerpy)

---

## test_package.py

**Purpose:** Smoke test that the `eventhandler` package is importable.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_import` | `eventhandler.baseclass.new` exists | Ensures the package is installed and the factory function is reachable. |

---

## test_classes.py

**Purpose:** Tests the ExampleRunner, ExampleDecider, logging, forward/timeout/spool lifecycle, and the end-to-end `handle()` method.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_example_runner` | `baseclass.new("example", ...)` creates `ExampleRunner` with correct attributes | Factory creates the right class with right config. |
| `test_example_decider` | `runner.new_decider()` creates `ExampleDecider` | Decider factory works. |
| `test_example_logging` | Logger is created with correct name (`eventhandler_example`), 2 handlers, and correctly named log file | Logger is configured with correct name and handlers. |
| `test_example_decider_prepare_event` | `ExampleDecider.decide_and_prepare()` sets `summary` and `payload` from raw event | Decider contract is fulfilled: summary + payload are set. |
| `test_example_runner_run_nodiscard_nosummary` | End-to-end: non-discarded event → log contains summary, echo file contains content | Happy path: event is processed and output file is written. |
| `test_example_runner_run_discard_loud` | Loud discard → log contains "discarded: ..." message, no echo file | Loud discard produces a log message but no output. |
| `test_example_runner_run_discard_silent` | Silent discard → no discard message in log, no echo file | Silent discard produces zero noise. |
| `test_example_runner_explicit_outcomes` | `run_result()` returns tuples with correct success values for `True`/`False`/`None` | Return value normalization works. |
| `test_example_forwarder_failure_isolated` | `handle()` survives `RuntimeError` from forwarder and still returns `True` | Forwarder failures don't crash the handler. |
| `test_handle_suppresses_concurrent_attempt` | Concurrent `handle()` returns `None` when lock is already held | Threading lock prevents concurrent handling. |
| `test_example_runner_timeout` | Event with `delay=120` and `discard=True` → discarded before timeout | Discard takes precedence over timeout. |

---

## test_builtin_plugins_focus.py

**Purpose:** Tests the built-in plugin ecosystem (deciders, runners, loggers) through the factory and direct instantiation.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_builtin_deciders_handle_state_transitions` | Parameterized: (1) default decider discards OK state; (2) OMD decider sets heal command on CRITICAL attempt=1 | Both deciders implement correct decision logic. |
| `test_builtin_decider_modules_directly` | Direct instantiation of `DefaultDecider` and `OmdSiteSelfHealDecider` bypassing factory | Deciders can be instantiated directly for testing. |
| `test_builtin_runners_render_expected_commands` | BashRunner and NscWebRunner render correct command strings | Each runner produces the expected shell command. |
| `test_ssh_runner_instantiates_with_identity_file` | `SshRunner` instantiates with `identity_file` and resolves the path | Missing import bug is fixed; SSH runner works with identity files. |
| `test_handle_forwards_execution_results_and_survives_forwarder_errors` | `handle()` survives forwarder `RuntimeError`; forwarded event shaped correctly | Forwarder errors are non-fatal. |
| `test_concurrent_handle_attempt_is_suppressed` | Concurrent `handle()` suppressed when lock held | Threading lock prevents concurrent handling. |
| `test_notification_forwarder_handoff_failure_is_logged` | Forwarder failure during handoff is handled gracefully | Handoff failures are non-fatal. |
| `test_text_logger_fallback_is_used_when_logger_type_is_invalid` | Invalid `logger_type` triggers text logger fallback | Graceful fallback prevents startup crashes. |
| `test_eventhandler_logger_output_is_structured` | Logger output after `no_more_logging()` + `run_result()` includes "Logger initialized" | Logger lifecycle works. |
| `test_builtin_logger_modules_fallback_and_text_output` | Invalid `logger_type` triggers text logger fallback (duplicate) | Consistent fallback behavior. |

---

## test_loggers.py

**Purpose:** Tests the logger fallback and structured output for the eventhandler's `TextLogger` and `JsonLogger`.

### class TestLoggerFallback

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_text_logger_fallback_is_used_when_logger_type_is_invalid` | Invalid `logger_type` → text logger fallback with "falling back to text" log | Fallback is triggered and logged. |
| `test_builtin_logger_modules_fallback_and_text_output` | Same as above (duplicate) | Consistent fallback behavior. |

### class TestLoggerOutput

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_eventhandler_logger_output_is_structured` | Logger output after `no_more_logging()` + `run_result()` has "Logger initialized" | Logger is initialized and produces output. |

---

## test_contracts_deciders.py

**Purpose:** Tests all built-in deciders (`DefaultDecider`, `OmdSiteSelfHealDecider`) and their decision logic.

### class TestDefaultDecider

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_host_downtime_discard` | Default decider discards (loudly) when `HOSTDOWNTIME=True` | Host downtime triggers loud discard. |
| `test_service_downtime_discard` | Default decider discards (loudly) when `SERVICEDOWNTIME=True` | Service downtime triggers loud discard. |
| `test_attempt_2_discard` | Default decider discards (loudly) when `SERVICEATTEMPT=2` on non-OK | Second attempt triggers loud discard ("did not help"). |
| `test_attempt_3_silent_discard` | Default decider discards **silently** when `SERVICEATTEMPT=3` | Third attempt triggers silent discard (no noise). |
| `test_attempt_1_proceeds` | Default decider allows event to proceed when `SERVICEATTEMPT=1`, non-OK, no downtime | First attempt sets payload and summary for execution. |

### class TestOmdSiteSelfHealDecider

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_host_downtime_discard` | OMD decider discards (loudly) on `HOSTDOWNTIME=True` | Host downtime triggers loud discard. |
| `test_service_downtime_discard` | OMD decider discards (loudly) on `SERVICEDOWNTIME=True` | Service downtime triggers loud discard. |
| `test_attempt_2_discard` | OMD decider discards (loudly) when `SERVICEATTEMPT=2` | Second attempt triggers loud discard. |
| `test_attempt_3_loud_discard` | OMD decider discards **loudly** at attempt=3 (differs from default's silent) | OMD decider is louder than default at attempt 3. |
| `test_attempt_1_payload` | OMD decider sets `user=site` and command containing `check_omd --heal` on attempt=1 | OMD decider injects site-specific healing command. |

### class TestOwnDeciderSmoke

AI-agent template tests demonstrating how to write a new decider.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_own_decider_sets_payload_and_summary` | Template: new decider must set both `event.payload` (dict) and `event.summary` (string) | Decider contract: payload + summary. |
| `test_own_decider_discard` | Template: decider discard path | Decider contract: discard works. |

---

## test_contracts_runners.py

**Purpose:** Tests all built-in runners (bash, ssh, nsc_web) and their command rendering.

### class TestBashRunner

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_basic_command` | Bash runner wraps a command as `bash -c '...'` | Command wrapping works. |
| `test_payload_command_override` | Bash runner does NOT use `event.payload["command"]` — it uses `self.command` | Documents that payload override is ignored for bash. |

### class TestNscWebRunner

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_with_arguments` | NSC_web runner includes command and arguments in output | Full command with arguments is rendered. |
| `test_without_arguments` | NSC_web runner omits argument segment when none provided | Command without arguments is rendered. |
| `test_password_quoting` | NSC_web runner properly quotes passwords with special characters | Special characters in passwords are handled. |
| `test_payload_overrides_init` | NSC_web runner uses `overwrite_attributes()` to replace hostname/port/password from payload | Payload overrides work. |

### class TestRunnerCommandRendering

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_bash_runner_exact_wrapping` | Exact string format of bash runner output | The exact command format is documented. |

### class TestOwnRunnerSmoke

AI-agent template tests demonstrating how to write a new runner.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_own_runner_run_returns_command` | Template: `run()` returns a command string | Runner contract: return a string. |
| `test_own_runner_run_returns_true` | Template: runner returning `True` means success without subprocess | Runner contract: `True` = success. |
| `test_cross_handoff_event_shape` | Template: forward event must contain `NOTIFICATIONTYPE=EVENTHANDLER`, `NOTIFICATIONAUTHOR`, `eventhandler_success` | Forward event shape is documented. |

---

## test_orchestration_handle.py

**Purpose:** Tests the `handle()` orchestration pipeline: special service descriptions, run result processing, attribute overwriting, forward event shaping, handoff skipping, and concurrent handling.

### class TestSpecialServiceDesc

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_return_code_of_early_return` | `handle()` returns `True` immediately for SERVICEDESC matching "Return code of"; decider is never called | Special service descriptions are skipped. |
| `test_timed_out_early_return` | `handle()` returns `True` immediately for SERVICEDESC "Timed Out" | Timeout events are skipped. |

### class TestRunResult

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_run_returns_false_no_handoff` | `run()` returning `False` → `success=False`, no handoff | False means failure; no downstream forwarding. |
| `test_run_returns_none_no_more_logging` | `run()` returning `None` → triggers no-more-logging path | None is a valid return value. |
| `test_run_returns_command_subprocess_path` | `run()` returning a command string → subprocess execution path | String return triggers subprocess execution. |

### class TestOverwriteAttributes

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_payload_overrides_runner_attributes` | `overwrite_attributes()` replaces runner attributes from payload | Payload overwrites runner defaults. |
| `test_precedence_chain` | Precedence: `__init__` < `runneropt` < `payload` | Attribute precedence is documented and enforced. |

### class TestForwardEventShaping

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_build_forward_event_success` | Forward event on success: `NOTIFICATIONTYPE=EVENTHANDLER`, `SERVICESTATE=OK` | Success shape is correct. |
| `test_build_forward_event_failure` | Forward event on failure: `SERVICESTATE=CRITICAL` | Failure shape is correct. |
| `test_build_forward_event_host_state` | Host event: success maps `HOSTSTATE` to "UP"; failure keeps "DOWN" | Host events use HOSTSTATE instead of SERVICESTATE. |

### class TestHandoffSkipping

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_handoff_skipped_when_success_none` | Handoff skipped when `success=None` | None success doesn't trigger forwarding. |
| `test_handoff_skipped_without_forwarder` | Handoff skipped gracefully when no forwarder configured | Missing forwarder doesn't crash. |

### class TestHandleExecution

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_handle_forwards_execution_results_and_survives_forwarder_errors` | `handle()` forwards results and survives `RuntimeError` from forwarder | Forwarder errors are non-fatal. |
| `test_notification_forwarder_handoff_failure_is_logged` | Forwarder handoff failure doesn't crash `handle()` | Handoff failure is logged and swallowed. |
| `test_concurrent_handle_attempt_is_suppressed` | Concurrent `handle()` returns `None` when lock is held | Threading lock prevents concurrent handling. |

---

## test_integration_cross.py

**Purpose:** Cross-project integration tests verifying the eventhandler→notificationforwarder handoff, decider discard paths, and forward event shape.

### class TestRunnerSuccessForwarderFails

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_runner_success_forwarder_500_failure_notification` | Runner succeeds but forwarder throws `RuntimeError("HTTP 500")`; event shaped correctly, failure logged at critical | Forwarder failure during handoff: event is still shaped correctly, error is logged. |
| `test_runner_failure_forwarder_500_failure_notification` | Runner fails + forwarder 500; failure notification with `FAILED` state | Both runner and forwarder failures: combined failure state. |

### class TestDeciderDiscardNoForward

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_decider_discard_no_forwarder_invoked` | Decider discards → forwarder never called | Discard path prevents forwarding. |
| `test_decider_discard_no_notification_log_activity` | Decider discard (SERVICEDOWNTIME=True) → no forwarder invocation | Downtime discard prevents forwarding. |

### class TestForwardEventShape

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_success_forward_event_shape` | Full forward event shape on success: includes stdout in `NOTIFICATIONCOMMENT`, preserves original fields | Success event has all expected fields. |
| `test_failure_forward_event_shape` | Forward event shape on failure: `SERVICESTATE=CRITICAL` | Failure event has correct state. |
| `test_host_event_forward_shape` | Host-only event: uses `HOSTSTATE` instead of `SERVICESTATE` | Host events are shaped correctly. |

---

## test_notify.py

**Purpose:** End-to-end integration tests with a real HTTP server, testing the full eventhandler→notificationforwarder→webhook pipeline.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_eventhandler_success_notification` | Full pipeline: eventhandler subprocess with `delay=5`, successful example runner, webhook forwarder to local HTTP server | Happy path end-to-end: event → runner → forwarder → HTTP server. Verifies: returncode 0, output file exists with correct content, delay is respected, all logs contain expected messages, received payload has correct fields. |
| `test_eventhandler_failure_notification` | Full pipeline: runner command writes to nonexistent path → failure; webhook still receives failure notification | Failure path end-to-end: event → runner (fails) → forwarder → HTTP server. Verifies: returncode 1, output file doesn't exist, logs contain "CRITICAL - run failed" and "No such file or directory", received payload has signature and description. |

---

## test_logger.py

**Purpose:** Unit tests for `TextLogger` and `JsonLogger` using `unittest.TestCase` style. Smoke tests for all logging call paths.

### class TestEventhandlerTextLogger

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_simple_message` | TextLogger logs at info/debug/warning/critical without errors | All log levels work. |
| `test_message_with_exception` | TextLogger logs with exception context | Exception context is handled. |
| `test_message_with_decided_event` | TextLogger logs with `DecidedEvent`, stdout, stderr, exit_code context | Event context is rendered. |
| `test_message_with_command` | TextLogger logs a command execution message at debug | Command logging works. |

### class TestEventhandlerJsonLogger

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_simple_json_message` | JsonLogger logs a simple message at info | Basic JSON logging works. |
| `test_json_with_event_context` | JsonLogger logs with `DecidedEvent`, runner_name, stdout, stderr, exit_code | Event context is serialized. |
| `test_json_with_exception` | JsonLogger logs with exception, exc_info, stderr, exit_code | Exception context is serialized. |
| `test_json_with_decider_context` | JsonLogger logs with decider_name and action at debug | Decider context is serialized. |
| `test_json_structure` | JsonLogger logs at critical with full context | Complex context is serialized. |

### class TestEventhandlerLoggerIntegration

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_text_logger_instantiation` | `baseclass.new()` with `logger_type='text'` succeeds | Text logger is instantiable via factory. |
| `test_json_logger_instantiation` | `baseclass.new()` with `logger_type='json'` succeeds | JSON logger is instantiable via factory. |
| `test_logger_fallback_for_invalid_type` | Invalid `logger_type` falls back to text and logs it | Graceful fallback is logged. |
