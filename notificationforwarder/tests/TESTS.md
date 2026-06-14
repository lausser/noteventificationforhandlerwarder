# notificationforwarder Test Suite

This document describes every test file, test case, and the code paths they cover.

**Audience:** Engineers reading these tests to understand *what* is being verified and *why* — not just what the assertion says.

**Conventions:**
- All tests require `OMD_ROOT` to be set; fixtures handle this automatically.
- `monkeypatch` is used to intercept external I/O (SMTP, HTTP, SQLite) and base-class loggers.
- `FormattedEvent` instances are created via dicts passed to `format_event()`.
- `nostr` tests use `pytest.importorskip("nostr_sdk")` for CI safety.

---

## Table of Contents

- [test_package.py](#test_packagepy)
- [test_loading_resolution.py](#test_loading_resolutionpy)
- [test_runtime_foundation.py](#test_runtime_foundationpy)
- [test_orchestration_flow.py](#test_orchestration_flowpy)
- [test_resilience_spool.py](#test_resilience_spoolpy)
- [test_contracts_formatters.py](#test_contracts_formatterspy)
- [test_contracts_forwarders.py](#test_contracts_forwarderspy)
- [test_contracts_reporters.py](#test_contracts_reporterspy)
- [test_loggers.py](#test_loggerspy)
- [test_nostr.py](#test_nostrpy)
- [test_integration_cli.py](#test_integration_clipy)
- [test_builtin_plugins_focus.py](#test_builtin_plugins_focuspy)
- [test_discard.py](#test_discardpy)
- [test_delivery_resilience.py](#test_delivery_resiliencepy)
- [test_webhook.py](#test_webhookpy)
- [test_alertmanager.py](#test_alertmanagerpy)
- [test_classes.py](#test_classespy)
- [test_formatter.py](#test_formatterpy)
- [test_paths.py](#test_pathspy)
- [test_oauth2webhook.py](#test_oauth2webhookpy)
- [test_reporter.py](#test_reporterpy)
- [test_logger.py](#test_loggerpy)

---

## test_package.py

**Purpose:** Smoke test that the `notificationforwarder` package is importable.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_import` | `notificationforwarder.baseclass.new` exists | Ensures the package is installed and the factory function is reachable. |

---

## test_loading_resolution.py

**Purpose:** Tests the dynamic component loading system (`component_loader.py`) that resolves and imports forwarders, formatters, and loggers by name at runtime.

### class TestResolveComponent

Pure-function tests for `resolve_component()`.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_derived_naming_underscore` | `my_thing` + `Forwarder` → module=`my_thing`, class=`MyThingForwarder`, rule=`derived-class` | Underscore-separated names are title-cased and concatenated with the suffix. |
| `test_derived_naming_simple` | `webhook` + `Formatter` → module=`webhook`, class=`WebhookFormatter`, rule=`derived-class` | Single-word names are title-cased. |
| `test_explicit_dotted_name` | `my.module.MyClass` → module=`my.module`, class=`MyClass`, rule=`explicit-class` | Explicit dotted notation is passed through without modification. |
| `test_explicit_dotted_preserves_class` | Class name `CustomFormatter` is not normalized | Explicit class names respect the author's casing. |
| `test_single_word` | `syslog` + `Forwarder` → class=`SyslogForwarder` | Single-word resolution produces the expected CamelCase. |

### class TestLoadForwarder

Integration tests for `load_forwarder()` using the `pythonpath/lib/python` test fixtures.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_loads_from_pythonpath` | Loads `Split1Forwarder` from `pythonpath/lib/python` | Verifies that the loader searches `sys.path` in order. |
| `test_local_overrides_lib` | Local `pythonpath/local/lib/python` takes precedence for `split2` | Local overrides shadow shared libraries. |
| `test_missing_forwarder_raises` | Non-existent forwarder raises `ComponentLoadError` | Missing modules fail with a descriptive error. |
| `test_details_include_component_name` | `ComponentLoadError.details` contains `component_name` and `component_type` | Error details are structured for programmatic consumption. |

### class TestLoadFormatter

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_loads_from_pythonpath` | Loads `VongFormatter` from `pythonpath/local/lib/python` | Formatter loading follows the same pythonpath rules. |
| `test_missing_formatter_raises` | Non-existent formatter raises `ComponentLoadError` | Consistent error behavior across component types. |
| `test_details_include_resolution_rule` | Error details include `resolution_rule == "derived-class"` | The resolution rule is recorded for diagnostics. |

### class TestLoadApplicationLogger

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_valid_logger_type` | `logger_type="text"` returns a `TextLogger` instance | Known logger types are loaded correctly. |
| `test_invalid_type_falls_back_to_text` | Unknown logger type returns `TextLogger` | Graceful fallback prevents startup crashes. |

---

## test_runtime_foundation.py

**Purpose:** Tests `RuntimeConfig`, `resolve_component`, and the `new()` factory for runtime setup, path computation, and forwarder instantiation.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_runtime_config_normalizes_forwarder_options` | `RuntimeConfig.from_inputs()` merges CLI opts with env vars, normalizes names, builds paths | Env vars (`NOTIFICATIONFORWARDER_LOGFILE_BACKUPS`, `NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES`) are used as defaults but CLI values take precedence. |
| `test_resolve_component_supports_derived_and_explicit_names` | `resolve_component()` handles both derived and explicit class resolution | The same function works for both naming styles. |
| `test_new_uses_text_logger_fallback_for_unknown_logger` | Unknown `logger_type` falls back to `TextLogger` with a warning log | The system never crashes on an invalid logger type. |
| `test_new_creates_forwarder_formatter_and_runtime_paths` | `baseclass.new()` instantiates the correct forwarder and formatter, resolves module files, computes db/lock paths | End-to-end factory test: name → module → class → paths. |
| `test_forward_runs_current_orchestration_flow` | `forward()` executes: log submission → format → forward → stamp `omd_originating_*` fields | The full orchestration pipeline works end-to-end. |

---

## test_orchestration_flow.py

**Purpose:** Tests the forward/discard pipeline, split-event handling, and the discard policy at the orchestration layer.

### class TestDiscardExtended

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_downtimeend_silent` | `discard(silently=True)` → event is NOT forwarded, nothing logged | Silent discards produce zero noise. |
| `test_downtimecancelled_loud` | `discard(silently=False)` → event is NOT forwarded, but "discarded" info log appears | Loud discards inform the operator. |
| `test_loud_discard_without_summary_dumps_raw` | Loud discard with `summary=None` still logs "discarded" using raw event as fallback | No crash when summary is missing; raw event is the fallback. |

### class TestRuntimeFoundationExtended

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_forwarder_forwarder_split_events` | `forward_multiple()` with 2 splits → 2 submits | Each split event is processed independently. |
| `test_forward_split_events_exception_no_delivery` | `split_events()` raising `RuntimeError` → 0 submits, critical log | An exception in split aborts the whole batch; no partial delivery. |

---

## test_resilience_spool.py

**Purpose:** Tests the spool (SQLite-backed event persistence) system including heartbeat policies, probe-gated flush, enrichment, formatter failure handling, and SpoolStore operations.

### class TestHeartbeatSpoolPolicy

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_webhook_heartbeat_failure_no_spool` | Heartbeat event (`is_heartbeat=True`) failing delivery is NOT spooled | Heartbeats are cheap; no point retrying them. |
| `test_webhook_non_heartbeat_failure_spools` | Non-heartbeat event failing delivery IS spooled | Real events must be retried. |

### class TestProbeGatedFlush

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_flush_skipped_when_probe_fails` | `probe()` returns `False` → flush is not called | Flush is gated by a health check; if the backend is down, don't bother flushing. |
| `test_flush_runs_when_probe_succeeds` | `probe()` returns `True` → flush runs | Healthy backend triggers spool replay. |

### class TestEnrichment

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_strips_unexpanded_macros` | `$HOSTNAME$` and `$` are removed from enriched event | Unexpanded Nagios macros are cleaned up. |
| `test_preserves_nested_structures` | Nested dicts and lists survive enrichment | Enrichment doesn't flatten complex values. |
| `test_adds_omd_metadata` | Enrichment adds `omd_site`, `omd_originating_host`, `omd_originating_fqdn`, `omd_originating_timestamp` | Every event gets OMD context stamped on it. |

### class TestFormatterFailure

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_incomplete_formatted_event_aborts` | Formatter sets `payload` but not `summary` → critical log with "incomplete", forwarding aborts | Incomplete events are never submitted. |
| `test_formatter_exception_no_spool` | `new_formatter()` raising `ValueError` → event is not spooled | Formatter errors are not retryable; no spooling. |
| `test_missing_formatter_module_aborts` | `load_formatter` raising `ComponentLoadError` → critical log, forwarding aborts gracefully | Missing formatter module is a configuration error, not a transient failure. |

### class TestSpoolReplayEdges

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_discarded_event_deleted_with_trash_log` | Spooled event returning a discarded `FormattedEvent` during replay is skipped and deleted, not submitted | The flush loop checks `is_discarded` and treats discarded events as trash. |
| `test_persistent_failure_keeps_row_and_terminates` | `submit()` always returning `False` → event stays in spool, stuck detection fires | Persistent failures are not silently dropped; the system logs and stops retrying. |
| `test_spool_init_failure_returns_false` | `SpoolStore.enqueue` raising `sqlite3.OperationalError` → returns `False` with "database error" log | Database errors are caught and logged, not raised. |
| `test_flush_beyond_batch_limit_stuck_detection` | 12 spooled events (exceeds batch limit of 10) with all submits failing → stuck detection, all events stay | The stuck detection logic handles batch boundaries correctly. |
| `test_formatter_returns_none_during_replay_deletes_trash` | `format_event` returning `None` during replay → event deleted as trash | Un-formattable events are cleaned up, not retried forever. |
| `test_summary_logging_resumes_after_flush` | `baseclass_logs_summary` is reset to `True` at flush start | The no_more_logging flag is reset so operators see summary logs after recovery. |

### class TestSpoolStore

Low-level `SpoolStore` operations against a real SQLite database.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_enqueue_and_fetch` | Enqueue 1 event, fetch 1 event | Basic round-trip. |
| `test_fetch_batch_limit` | `fetch_batch(limit=10)` returns 10 of 15 enqueued | Batch limit is respected. |
| `test_delete_nonexistent_event` | `delete(99999)` is a no-op | Deleting a missing ID doesn't crash. |
| `test_count_accuracy` | Count is accurate after enqueue, enqueue, and delete | `count()` reflects the true state. |
| `test_fetch_batch_limit_zero` | `fetch_batch(limit=0)` returns `[]` | Zero limit is handled. |
| `test_fetch_batch_limit_exceeds_total` | Limit exceeding total returns all rows | No error when limit is too high. |
| `test_prune_expired_boundary` | `prune_expired(5)` deletes only events strictly older than 5 minutes | Boundary conditions are correct. |
| `test_enqueue_non_serializable_data` | Enqueuing a `set` raises `TypeError` | Non-JSON-serializable data is rejected. |
| `test_decode_round_trip` | JSON encode → decode produces the original dict | Serialization preserves data. |
| `test_concurrent_enqueue` | Two threads each enqueuing 10 events concurrently → 20 rows, no corruption | Thread safety of concurrent writes. |
| `test_concurrent_enqueue_shared_instance` | Shared SpoolStore instance across threads documents SQLite cursor limitation | SQLite doesn't allow recursive cursor use; the real forwarder uses file locks. |

---

## test_contracts_formatters.py

**Purpose:** Tests all built-in formatters (email, syslog, rabbitmq, example, vong, alertmanager_servicenow) and their edge cases.

### class TestBuiltinFormatters

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_email_formatter_html_and_text` | Email formatter produces `html`, `text`, `subject` in payload; summary is `"mail"` | The formatter renders all email parts correctly. |
| `test_syslog_formatter_host_event` | Syslog formatter produces `host:state` summary and combined output string | Host events are formatted correctly. |
| `test_rabbitmq_formatter_queue_event` | RabbitMQ formatter produces list payload with `host_name` and `state` keys | Queue events have the expected structure. |
| `test_example_formatter_with_signature` | Example formatter produces `summary`, `payload` dict with `description`, `signature`, `timestamp` | Reference formatter works as documented. |

### class TestEmailFormatterEdges

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_host_only_notification` | Email formatter handles host-only events (no `SERVICEDESC`) | Host-only events use host templates, not service templates. |
| `test_acknowledgement_block` | Email formatter renders `ACKAUTHOR` and `ACKCOMMENT` for `ACKNOWLEDGEMENT` notification type | Acknowledgements include author/comment blocks. |
| `test_notification_comment` | Email formatter renders `NOTIFICATIONCOMMENT` for non-ACK notifications | Notification comments are included when present. |
| `test_missing_optional_macros` | Email formatter handles missing `LONGSERVICEOUTPUT` and `CONTACTEMAIL` gracefully | Missing optional fields don't cause crashes. |

### class TestSyslogFormatterEdges

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_host_event` | Syslog formatter includes hostname, state, output for host events | Host events have complete output in the payload string. |

### class TestOwnFormatterSmoke

AI-agent template tests demonstrating how to write a new formatter.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_own_formatter_produces_payload_and_summary` | VongFormatter produces `payload` dict, non-empty `summary`, and `host_name` key | Template: new formatter must set both `payload` and `summary`. |
| `test_own_formatter_host_only_event` | VongFormatter handles host-only events (no `SERVICEDESC`) | Template: host-only events must not crash. |
| `test_multiline_output` | Syslog formatter preserves `\n`-delimited multiline output | Multiline output is not collapsed or escaped. |

---

## test_contracts_forwarders.py

**Purpose:** Tests all built-in forwarders (email, syslog, telegram, webhook) and their edge cases, plus AI-agent template smoke tests.

### class TestEmailForwarder

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_smtp_success_with_html_and_text` | Email forwarder sends MIME with both html and text parts; `sendmail` and `quit` called once | Full MIME construction works. |
| `test_html_only_payload` | Email forwarder sends HTML-only MIME when no `text` key | Missing text part is handled. |
| `test_text_only_payload` | Email forwarder sends text-only MIME when no `html` key | Missing html part is handled. |
| `test_missing_body_fallback` | Email forwarder sends fallback message when neither `html` nor `text` provided | Total absence of body is handled gracefully. |
| `test_smtp_exception_returns_false` | `SMTPException` from SMTP constructor returns `False` | Connection failures are caught. |
| `test_failure_spools_non_heartbeat` | On SMTP failure, base class spools the raw event for non-heartbeat events | Failed deliveries are persisted for retry. |

### class TestSyslogForwarder

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_facility_normalization` | `"local0"` and `"log_local0"` resolve to the same facility value | Both naming conventions work. |
| `test_invalid_facility_fallback` | Unknown facility name falls back to `LOG_DAEMON` | Invalid names don't crash; sensible default is used. |
| `test_priority_normalization` | `"info"` and `"log_info"` resolve to the same priority value | Both naming conventions work. |
| `test_invalid_priority_fallback` | Unknown priority name falls back to `LOG_INFO` | Invalid names don't crash. |
| `test_submit_exception_returns_false` | Exception from `SysLogHandler.log()` returns `False` | Syslog errors are caught. |

### class TestTelegramForwarder

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_submit_success` | Successful Telegram API call (status 200) returns `True` | Happy path works. |
| `test_submit_http_failure` | Non-200 status (400) returns `False` | HTTP errors are caught. |
| `test_submit_timeout_status` | Timeout status codes (408, 504) return `False` | Timeout-like statuses are treated as failures. |
| `test_list_payload_all_success` | `submit()` with list, all `submit_one` succeed → returns `True` | List payloads work end-to-end. |
| `test_list_payload_partial_failure` | Any `submit_one` in a list fails → returns `False` | Partial failure is treated as total failure. |
| `test_heartbeat_no_spool` | Heartbeat events are NOT spooled on Telegram failure | Heartbeat retry policy is enforced. |
| `test_failure_spools_non_heartbeat` | Non-heartbeat events ARE spooled on Telegram failure | Non-heartbeat retry policy is enforced. |

### class TestWebhookForwarder

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_submit_one_supports_modes_and_overrides` | Webhook `submit_one` supports `json`, `form`, and `raw` modes; URL/headers/auth overrides work | All three content modes and per-event overrides work. |
| `test_forward_failure_spools_and_handles_spool_errors` | HTTP 500 → event spooled; spool failure → no crash | Spooling is attempted; spool failure is non-fatal. |

### class TestWebhookExtended

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_accepted_created_status` | Status codes 201 and 202 are treated as success | 2xx codes beyond 200 are accepted. |
| `test_insecure_verify_disabled` | `insecure=yes` passes `verify=False` to `requests.post` | SSL verification toggle works. |
| `test_url_override_from_event` | `event.forwarderopts["url"]` overrides the configured URL | Per-event URL override works. |
| `test_headers_merge` | Base headers and per-event headers are merged | Header merging works without loss. |
| `test_timeout_exception_returns_false` | `requests.exceptions.Timeout` during POST returns `False` | Timeout is caught. |
| `test_content_type_header_precedence` | User-provided `Content-Type` is not overwritten by mode default | User headers take precedence. |
| `test_url_mutation_side_effect` | URL override from the first event permanently mutates `self.url` | Documents the URL mutation side effect. |
| `test_header_case_insensitive_merge` | `Content-type`, `content-Type`, `CONTENT-TYPE` variants all prevent the default `Content-Type` from being added | Case-insensitive header matching works. |
| `test_raw_mode_list_payload` | Raw mode with a list payload sends `json.dumps(list)` as the `data` kwarg | List payloads in raw mode are serialized correctly. |

### class TestOwnForwarderSmoke

AI-agent template tests demonstrating how to write a new forwarder.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_own_forwarder_submit_success` | ExampleForwarder `submit()` returns a boolean | Template: `submit()` must return `True`/`False`. |
| `test_own_forwarder_failure_spools_for_non_heartbeat` | Non-heartbeat submission failure triggers spooling | Template: failure path invokes spool. |
| `test_own_forwarder_heartbeat_failure_no_spool` | Heartbeat submission failure does NOT trigger spooling | Template: heartbeat policy is respected. |

### class TestOwnFullTargetSmoke

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_formatter_forwarder_pair` | End-to-end: VongFormatter formats an event, then webhook forwarder receives the formatted event with correct payload | Formatter and forwarder can be paired without glue code. |

---

## test_contracts_reporters.py

**Purpose:** Tests the `NaemonlogReporter` and its edge cases.

### class TestNaemonlogReporter

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_writes_expected_host_and_service_lines` | Naemonlog reporter writes correct `HOST NOTIFICATION` and `SERVICE NOTIFICATION` lines | The output format matches Naemon's expected syntax. |
| `test_missing_command_file_silent_noop` | Reporter with empty opts dict does not raise | Missing configuration is handled gracefully. |
| `test_default_contact_name_global` | When `CONTACTNAME` is absent, `"GLOBAL"` is used as default | Default values fill in missing fields. |
| `test_explicit_command_file_appends_log_line` | Command file gets `LOG;` prefix prepended | The Naemon command file format includes the `LOG;` prefix. |
| `test_host_vs_service_default_notification_command` | Host events use `global_host_notification_handler`, service events use `global_service_notification_handler` | Default notification commands differ by event type. |
| `test_unknown_reporter_critical_logs_but_forwarding_unaffected` | Unknown reporter name causes a critical log but doesn't break forwarding | Reporter failures are non-fatal to the forwarder pipeline. |
| `test_no_config_anywhere_silent_noop` | No `command_file` in opts and no readable `naemon.cfg` = silent no-op | Complete absence of configuration is handled gracefully. |
| `test_failure_suffix_appended` | When `forwarder_success=False`, suffix `"(could not be forwarded to webhook)"` is appended | Failure notifications include the destination in the suffix. |

---

## test_loggers.py

**Purpose:** Tests `TextLogger` and `JsonLogger` message branches. These are primarily smoke/crash-coverage tests ensuring all logging call paths render without exceptions.

### class TestTextLogger

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_simple_message` | TextLogger handles `info`, `debug`, `warning`, `critical` with empty context | All log levels work without context. |
| `test_message_with_exception` | TextLogger handles `critical` with exception context | Exception context doesn't crash. |
| `test_message_with_formatted_event` | TextLogger handles `info` with a `FormattedEvent` in context | Event context is rendered. |
| `test_message_with_spooled_event` | TextLogger handles `critical` with exception + `FormattedEvent` + `spooled=True` | Combined context works. |

### class TestJsonLogger

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_simple_json_message` | JsonLogger handles `info` with empty context | Basic JSON logging works. |
| `test_json_with_event_context` | JsonLogger handles `info` with `FormattedEvent` and status | Event context is serialized. |
| `test_json_with_exception` | JsonLogger handles `critical` with exception and `exc_info` | Exception context is serialized. |
| `test_json_with_spooled_context` | JsonLogger handles `warning` and `info` with spooling context fields | Spooling context is serialized. |
| `test_json_structure` | JsonLogger handles `critical` with rich context dict | Complex context is serialized without error. |

### class TestTextLoggerMessageBranches

Smoke tests for every logging call path in `baseclass.py`. Each test calls a specific log message to ensure it doesn't crash.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_flush_probe_failed` | `critical("flush probe failed", ...)` renders | Flush probe failure path is covered. |
| `test_database_flush_resubmit_failed` | `critical("database flush+resubmit failed", ...)` renders | Database flush failure path is covered. |
| `test_found_no_formatter_module` | `critical("found no formatter module", ...)` renders | Missing formatter module path is covered. |
| `test_spool_replay_summary` | `info("spool replay summary", ...)` renders | Replay summary path is covered. |
| `test_delete_spooled_event_action` | `info("delete spooled event", ...)` renders | Spool deletion path is covered. |
| `test_event_stays_in_spool_action` | `critical("event stays in spool", ...)` renders | Persistent failure path is covered. |
| `test_delete_trash_event_action` | `info("delete trash event", ...)` renders | Trash deletion path is covered. |
| `test_could_not_format_spooled_event_action` | `critical("could not format spooled event", ...)` renders | Un-formattable spooled event path is covered. |
| `test_dropped_outdated_events_action` | `info("dropped outdated events", ...)` renders | Expired event pruning path is covered. |
| `test_concurrent_flush_suppressed` | `info("concurrent flush suppressed", ...)` renders | Concurrent flush suppression path is covered. |
| `test_spooled_events_to_be_resent` | `info("spooled events to be re-sent", ...)` renders | Spool replay initiation path is covered. |
| `test_spooled_events_could_not_be_submitted` | `critical("spooled events could not be submitted", ...)` renders | Persistent submission failure path is covered. |
| `test_delivery_failed_could_not_persist` | `critical("delivery failed and event could not be persisted", ...)` renders | Unrecoverable failure path is covered. |
| `test_formatted_event_incomplete` | `critical("formatted event incomplete", ...)` renders | Incomplete event path is covered. |

### class TestJsonLoggerStructuredFields

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_success_structured_fields` | JsonLogger `info("forwarded", ...)` with event, status, forwarder_name, split_count renders structured JSON | Success path JSON structure is correct. |
| `test_failure_structured_fields` | JsonLogger `critical("forward failed", ...)` with exception, event, spooled, forwarder_name, attempt renders structured JSON | Failure path JSON structure is correct. |

---

## test_nostr.py

**Purpose:** Tests the Nostr integration (formatter, forwarder, DM delivery, key handling). Requires `nostr_sdk` — tests are skipped if not available.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_nostr_formatter_builds_readable_message` | NostrFormatter produces correct human-readable message body, tags, and summary | The formatter produces readable Nostr events. |
| `test_nostr_forwarder_builds_dm_event` | Nostr forwarder constructs and sends a DM event via the SDK | Happy path: DM is sent successfully. |
| `test_nostr_forwarder_logs_failure_without_secret` | Forwarder logs error and returns `False` when SDK raises RuntimeError | Relay failures are caught and logged. |
| `test_nostr_forwarder_handles_invalid_sdk_message` | Forwarder returns `False` and logs when SDK rejects a message | SDK rejections are caught. |
| `test_nostr_forwarder_uses_configured_recipient_tag` | Forwarder uses the `p` tag from config to determine DM recipient | Recipient is taken from event tags. |
| `test_nostr_forwarder_requires_nostr_sdk` | When `nostr_sdk` is not importable, import fails with ImportError | Missing SDK produces a clear error. |
| `test_nostr_forwarder_clamps_websocket_timeout_and_still_initializes` | Forwarder still initializes and sends DMs even with websocket timeout clamping | Timeout clamping doesn't break functionality. |
| `test_nostr_forwarder_fails_without_recipient_tag` | Submitting without a `p` tag raises `ValueError` mentioning "recipient p tag" | Missing recipient is caught early. |

### class TestNostrMissingPTag

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_missing_p_tag_fails_with_recipient_mention` | Missing `p` tag raises ValueError with "recipient p tag" | Consistent error message for missing recipient. |
| `test_missing_p_tag_spools_via_forward` | Missing `p` tag in format_event result → event is spooled | Missing recipient triggers spool, not crash. |

### class TestNostrHostOnlyEvent

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_host_only_event_uses_service_dash` | Host-only event (no SERVICEDESC) uses `"-"` as service | Host-only events have a sensible default. |
| `test_host_only_event_tags_only_host_and_state` | Host-only event tags include host and state but no service tag | Service tag is omitted for host events. |

### class TestNostrFieldAliases

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_host_alias` | `HOST` alias produces the same output as `HOSTNAME` | Field aliases work interchangeably. |
| `test_service_alias` | `SERVICE` alias produces the same output as `SERVICEDESC` | Field aliases work interchangeably. |
| `test_state_alias` | `STATE` alias produces the same output as `SERVICESTATE` | Field aliases work interchangeably. |
| `test_output_alias` | `OUTPUT` alias produces the same output as `SERVICEOUTPUT` | Field aliases work interchangeably. |

### class TestNostrNpubNormalization

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_npub1_normalized_to_hex_via_sdk` | `nostr_sdk.PublicKey.parse()` can parse npub1-formatted keys | npub1 format is handled by the SDK. |
| `test_npub_in_p_tag_works_for_submit` | npub1 format in `p` tag is accepted and submit succeeds | npub1 format works end-to-end. |

### class TestNostrNsecNotInLogs

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_nsec_not_in_logs_on_success` | The nsec never appears in logs after a successful send | Secrets are never leaked to logs. |
| `test_nsec_not_in_logs_on_failure` | The nsec never appears in logs after a failed send | Secrets are never leaked even on error. |

### class TestNostrRelayFailureSpools

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_relay_publish_failure_spools_event` | When relay publish fails, `forward()` spools the event | Relay failures trigger spooling for retry. |

---

## test_integration_cli.py

**Purpose:** Tests the CLI entry points (`notificationforwarder` and `eventhandler` binaries).

### class TestNotificationForwarderCLI

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_nf_exists_and_requires_omd` | The `notificationforwarder` binary exists and produces output mentioning "OMD" or exits 0 | The binary is installed and recognizes the OMD requirement. |
| `test_nf_missing_forwarder_defaults_to_syslog` | Running without `--forwarder` defaults to syslog and exits successfully | The `--forwarder` argument has a default value. |

### class TestEventHandlerCLI

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_eh_exists_and_requires_omd` | The `eventhandler` binary exists and produces output mentioning "OMD" or exits 0 | The binary is installed. |
| `test_eh_missing_runner_nonzero` | Running without `--runner` produces a non-zero exit code | Missing required argument is caught. |

---

## test_builtin_plugins_focus.py

**Purpose:** Tests the built-in plugin ecosystem (formatters, forwarders, reporters, loggers) through the `baseclass.new()` factory, verifying instantiation and basic behavior.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_builtin_formatters_render_expected_payloads` | All four built-in formatters (email, syslog, rabbitmq, example) produce expected summary and payload structure | Each formatter renders the correct output format. |
| `test_webhook_submit_one_supports_modes_and_overrides` | Webhook `submit_one` supports `json`, `form`, `raw` modes; URL/header/auth overrides work | Mode and override mechanics work. |
| `test_webhook_forward_failure_spools_and_handles_spool_errors` | HTTP 500 → spool; spool failure → no crash | Error handling chain works. |
| `test_telegram_forwarder_list_and_heartbeat_paths` | Telegram `submit()` with list and heartbeat events | List and heartbeat policies work. |
| `test_telegram_forwarder_submit_one_failure_returns_false` | Telegram `submit_one` returns `False` when no backend is reachable | Failure path returns `False`. |
| `test_naemonlog_reporter_writes_expected_host_and_service_lines` | NaemonlogReporter writes correct notification lines | Reporter output format is correct. |
| `test_builtin_logger_modules_format_text_and_json` | TextLogger and JsonLogger can be instantiated and called without errors | Logger modules are importable and functional. |

---

## test_discard.py

**Purpose:** Tests the discard mechanism via the CLI binary with the `discard` formatter.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_discard_do_not_discard` | Event NOT discarded → forwarded normally, signature in log | Normal events pass through. |
| `test_discard_discard_silently` | `was_i_machn_tu="dem maul haltn"` → silently discarded, nothing logged | Silent discard produces zero output. |
| `test_discard_discard_with_own_comment` | `was_i_machn_tu="dem semf dazugebn"` → discarded with custom comment | Loud discard with custom message. |
| `test_discard_discard_with_default_comment` | `was_i_machn_tu="dem automatischn semf dazugebn"` → discarded with default comment | Loud discard with default message. |

---

## test_delivery_resilience.py

**Purpose:** Tests the delivery failure handling, spool persistence, flush replay, timeout decorator, and concurrent flush suppression.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_failed_delivery_is_spooled_and_logged` | `submit()` failing → event spooled, CRITICAL + WARNING logs | Failure path: spool + logging. |
| `test_unrecoverable_failure_is_logged_when_spooling_fails` | Delivery fails AND `spool()` fails → CRITICAL "could not be persisted" | Double failure: delivery + spool. |
| `test_flush_replays_spooled_events_on_recovery` | New forwarder (no `fail`) triggers flush → spooled events replayed and deleted | Recovery path: flush + replay. |
| `test_flush_drops_expired_spooled_events` | Spooled events older than `max_spool_minutes` are dropped during flush | Expired events are cleaned up. |
| `test_flush_logs_when_concurrent_lock_is_unavailable` | Flush lock not acquired → "concurrent flush suppressed" log | Concurrent flush prevention works. |
| `test_timeout_decorator_raises_forwarder_timeout` | `@timeout` decorator raises `ForwarderTimeoutError` on timeout | Timeout enforcement works. |
| `test_timeout_decorator_preserves_underlying_exception` | Non-timeout exceptions propagate normally through `@timeout` | Timeout doesn't swallow other exceptions. |

---

## test_webhook.py

**Purpose:** End-to-end tests with a real HTTP server, testing the webhook forwarder with various formatters, auth modes, and event types.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_forward_webhook_format_rabbitmq` | Webhook + `rabbitmq` formatter sends JSON with `output` field | RabbitMQ formatter works end-to-end. |
| `test_forward_webhook_format_example` | Webhook + `example` formatter sends JSON with `signature`, `description`, `timestamp` | Example formatter works end-to-end. |
| `test_forward_webhook_format_vong` | Webhook + `vong` formatter sends JSON with `host_name` | Vong formatter works end-to-end. |
| `test_forward_webhook_format_bayern` | Webhook + `bayern` formatter sends JSON with `da_host` | Bayern formatter works end-to-end. |
| `test_forward_webhook_format_vong_bin_basic_auth` | Webhook + vong via CLI binary with Basic auth | CLI binary works with Basic auth. |
| `test_forward_webhook_format_vong_bin_token_auth` | Webhook + vong via CLI with Bearer token auth | CLI binary works with Bearer token. |
| `test_forward_webhook_format_vong_bin_token_auth_by_formatter` | Webhook + vong via CLI with formatter-injected Bearer token | Formatter-level auth injection works. |
| `test_submit_form_with_xml_payload` | Webhook `datapost` formatter in `form` mode sends form-encoded data | Form mode works end-to-end. |
| `test_forward_multiple_events` | `forward_multiple()` sends 2 events with sequential `split_id` values | Split events work end-to-end. |
| `test_forward_multiple_events_bin` | Same as above via CLI binary | CLI binary handles split events. |

---

## test_alertmanager.py

**Purpose:** End-to-end test for the Alertmanager-to-ServiceNow webhook pipeline.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_alertmanager_forwarder` | Alertmanager webhook forwarder processes a full payload with 2 alerts, logs node replacement and success | The full alertmanager pipeline works with real formatter logic. |

---

## test_classes.py

**Purpose:** Tests the ExampleForwarder class, its attributes, logging, formatter, and the forward/timeout/spool lifecycle.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_example_forwarder` | `baseclass.new("example", ...)` creates `ExampleForwarder` with correct attributes | Factory creates the right class with right config. |
| `test_example_logging` | Logger setup produces named logger with 2 handlers and correctly named log file | Logger is configured with correct name and handlers. |
| `test_example_formatter_format_event` | `ExampleFormatter.format_event()` sets `summary` and `payload` on a `FormattedEvent` | Formatter contract is fulfilled. |
| `test_example_forwarder_forward` | `forward()` logs submission and forwarding; `no_more_logging()` suppresses baseclass log | Forward pipeline works; log suppression works. |
| `test_example_forwarder_forward_success` | After successful forward, signature is written to signature file | Successful delivery produces the expected side effect. |
| `test_example_forwarder_forward_timeout` | `delay=60` causes timeout → event spooled; `delay=0` triggers flush → events replayed | Timeout → spool → recovery → flush lifecycle works. |

---

## test_formatter.py

**Purpose:** Tests formatter loading from different pythonpath layers and the runtime log file for formatter-specific logging.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_split1_forwarder` | Split1 forwarder from `pythonpath/lib/python`, Split4 formatter from `pythonpath/local/lib/python` | Different pythonpath layers are resolved correctly for forwarder vs formatter. |
| `test_split3_forwarder_split4_formatter` | Both Split3 forwarder and Split4 formatter from `pythonpath/local/lib/python` | Local overrides work for both components. |
| `test_formatter_module_logging_uses_runtime_logfile` | AlertmanagerServicenowFormatter writes to the runtime log file | Formatter-specific logging goes to the correct file. |
| `test_split3_forwarder_split4_formatter_bin_old` | CLI invocation writes signature with formatter naming convention | CLI binary works with split3/split4. |
| `test_split3_forwarder_split4_formatter_bin` | Same as above (variant) | CLI binary works consistently. |

---

## test_paths.py

**Purpose:** Tests that forwarders and formatters are loaded from the correct pythonpath layers.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_split1_forwarder` | Split1 forwarder from `lib/python`, Split1 formatter from `local/lib/python` | Different layers for forwarder vs formatter. |
| `test_split2_forwarder` | Split2 forwarder from `local/lib/python`, Split2 formatter from `lib/python` | Opposite layer priority. |
| `test_split3_forwarder` | Both Split3 forwarder and formatter from `local/lib/python` | Both overridden locally. |

---

## test_oauth2webhook.py

**Purpose:** Tests the OAuth2 token flow for webhook forwarders.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_token_acquired_and_used` | Token is acquired once and sent as Bearer auth to the API endpoint | Happy path: token → API call. |
| `test_cached_token_reused` | Fresh token in cache file is reused without calling token endpoint | Cache prevents redundant token requests. |
| `test_expired_cache_triggers_refresh` | Expired token cache triggers fresh token acquisition | Expired tokens are refreshed. |
| `test_token_failure_spools_event` | Token endpoint returns 404 → event spooled, API never called | Token failure triggers spool, not API call. |
| `test_tag_separates_token_cache` | Different forwarder tags produce different cache file paths | Tags isolate token caches. |

---

## test_reporter.py

**Purpose:** End-to-end tests for the naemonlog reporter with a real HTTP server, testing success and failure notification formatting.

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_forward_webhook_format_vong_bin_basic_auth` | Webhook + vong + naemonlog reporter: successful delivery writes payload AND HOST NOTIFICATION line | Reporter writes correct output on success. |
| `test_forward_webhook_format_vong_bin_basic_auth_fail` | Wrong password → failure; reporter writes notification with `(could not be forwarded to webhook)` and default GLOBAL contact | Reporter writes correct output on failure. |
| `test_reporter_payload_ok` | ticketsystem forwarder + vong + ticketsystem reporter: success appends signature to notification | Reporter appends custom payload on success. |
| `test_reporter_payload_fail` | ticketsystem forwarder with no signature → failure notification with `(could not be forwarded to ticketsystem)` | Reporter appends custom suffix on failure. |

---

## test_logger.py

**Purpose:** Unit tests for `TextLogger` and `JsonLogger` using `unittest.TestCase` style. Smoke tests for all logging call paths.

### class TestTextLogger

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_simple_message` | TextLogger logs at info/debug/warning/critical without errors | All log levels work. |
| `test_message_with_exception` | TextLogger logs with exception context | Exception context is handled. |
| `test_message_with_formatted_event` | TextLogger logs with `FormattedEvent` context | Event context is rendered. |
| `test_message_with_spooled_event` | TextLogger logs with exception + `FormattedEvent` + `spooled=True` | Combined context works. |

### class TestJsonLogger

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_simple_json_message` | JsonLogger logs a simple message | Basic JSON logging works. |
| `test_json_with_event_context` | JsonLogger logs with `FormattedEvent` context | Event context is serialized. |
| `test_json_with_exception` | JsonLogger logs with exception context | Exception context is serialized. |
| `test_json_with_spooled_context` | JsonLogger logs with spooling context | Spooling context is serialized. |
| `test_json_structure` | JsonLogger logs with rich context dict | Complex context is serialized. |

### class TestLoggerIntegration

| Test | What it verifies | Intention |
|------|------------------|-----------|
| `test_text_logger_instantiation` | `baseclass.new()` with `logger_type='text'` succeeds | Text logger is instantiable via factory. |
| `test_json_logger_instantiation` | `baseclass.new()` with `logger_type='json'` succeeds | JSON logger is instantiable via factory. |
