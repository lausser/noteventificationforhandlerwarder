## ADDED Requirements

### Requirement: The test suite itself makes the runtime architecture and extension model obvious
The system SHALL organize its automated tests in a flat structure using consistent layer-derived naming across the two sibling subprojects (notificationforwarder and eventhandler) so that the runtime layers (loading/resolution, runtime bootstrap/config/paths, orchestration/flow, resilience, contracts per extension point, loggers, integration) are immediately visible at directory listing time. The organization SHALL treat shipped modules and user-written modules in local/lib identically.

#### Scenario: A contributor or AI agent opens the tests directory
- **WHEN** a contributor or agent lists notificationforwarder/tests/ and eventhandler/tests/
- **THEN** they see a clear, flat set of files with consistent prefixes (test_loading_resolution.py, test_runtime_*.py, test_orchestration_*.py, test_resilience_*.py, test_contracts_formatters.py / forwarders.py / reporters.py (notificationforwarder only) / deciders.py / runners.py, test_loggers.py, test_integration_cross.py, etc.) and no empty or dummy files for concepts that do not exist in a subproject.

### Requirement: Contributor- and agent-facing contract smokes exist for own modules
The system SHALL provide a small set of tiny, heavily-commented "own module" contract smoke tests (using the exact same new()/handle() entry points and pythonpath fixtures as real user modules) that serve as copyable templates when a user or agent is asked to implement a formatter, forwarder, decider, or runner for an external system. These smokes SHALL demonstrate uniform treatment and the key contract surfaces (payload+summary, submit/forward/heartbeat/spool semantics, decide_and_prepare + discard, run() outcomes + payload override, cross-handoff event shape).

#### Scenario: An agent is told to implement a ticket-system integration
- **WHEN** an agent is given only the base class contract plus one of the tiny own-module smokes
- **THEN** the agent can produce correct, minimal tests for a new formatter/forwarder (nf) or decider/runner (eh) that exercise the same observable outcomes as the shipped examples.

### Requirement: Contributor-facing tests cover the full documented extension surface and runtime guarantees
The system SHALL provide automated tests that demonstrate expected behavior for component loading (explicit dotted class paths, missing forwarder/reporter error messages), logger fallback and all special message branches in _build_message, reporter instantiation failures and silent no-op paths (builtin naemonlog on notificationforwarder only), runtime configuration (env var fallbacks, forwardertag suffix naming for logs/db/locks), forwarder multiple/split events, discard extended patterns, oauth2 concurrency and token handling, and all extension points (formatters, forwarders, reporters (nf), deciders, runners, loggers) across both subprojects, with uniform coverage whether the module is shipped or user-provided.

#### Scenario: runtime-config-env-var-fallback
- **WHEN** NOTIFICATIONFORWARDER_LOGFILE_BACKUPS or MAX_SPOOL_MINUTES are set in the environment and omitted from forwarderopt
- **THEN** the env var values are used

#### Scenario: runtime-tag-suffix-paths
- **WHEN** --forwardertag is supplied
- **THEN** distinct log file, sqlite DB, and flush lock names are produced that incorporate the tag

#### Scenario: runtime-lockfile-naming-no-underscore
- **WHEN** a tag is present
- **THEN** the flush lock file name is constructed as notificationforwarder<forwarder_name><tag>_flush.lock (no _ before the tag) while the sqlite db still uses _

#### Scenario: component-loader-explicit-dotted-class
- **WHEN** a dotted module.class path is passed for a forwarder or reporter
- **THEN** it resolves via the explicit-class rule

#### Scenario: component-loader-missing-forwarder
- **WHEN** an unknown forwarder name is requested
- **THEN** an actionable ImportError message is raised

#### Scenario: component-loader-reporter-explicit-class
- **WHEN** --reporter is given as an explicit dotted path
- **THEN** the reporter class is loaded using the same resolution rule used for forwarders/formatters

#### Scenario: test-structure-makes-layers-obvious
- **WHEN** the tests directory is listed
- **THEN** the flat layer-prefixed files make the runtime architecture (loading, runtime, orchestration, resilience, contracts per extension point, loggers, integration) immediately comprehensible, with no reporter file or dummy reporter tests on the eventhandler side and no rabbitmq coverage in this change scope.

#### Scenario: forward-multiple-split-events
- **WHEN** a formatter implements split_events()
- **THEN** each returned raw event is formatted and forwarded independently

#### Scenario: forward-multiple-split-failure
- **WHEN** split_events() raises
- **THEN** a critical log is emitted and no partial delivery occurs

#### Scenario: forward-multiple-split-mixed-outcomes
- **WHEN** split_events() returns N raw events and some forward() calls succeed while others fail
- **THEN** overall forward_multiple does not abort the batch; independent outcomes are logged and only successful ones delete their spool rows on replay

#### Scenario: nf-json-logger-cli-success
- **WHEN** notificationforwarder is invoked with --logger json and a successful delivery occurs
- **THEN** the emitted log line is valid JSON containing event_host_name, event_service_name, and msg.status=success

#### Scenario: nf-json-logger-cli-failure-spool
- **WHEN** delivery fails and --logger json is used
- **THEN** the JSON log contains spool/queue related fields

#### Scenario: nf-json-logger-exception-trace
- **WHEN** a formatter or forwarder raises and --logger json is active
- **THEN** the structured traceback appears in the JSON output under msg.exception.trace or equivalent

#### Scenario: eh-json-logger-cli-success
- **WHEN** eventhandler is invoked with --logger json and a runner succeeds
- **THEN** the emitted JSON contains event_summary and execution status

#### Scenario: eh-json-logger-fallback
- **WHEN** an unknown logger type is requested for eventhandler
- **THEN** a text fallback warning appears in the log

#### Scenario: nf-text-logger-all-special-messages
- **WHEN** TextLogger (or full runs) emit every message string that has a dedicated branch in _build_message
- **THEN** each exact rendered text for "flush probe failed", "database flush+resubmit failed", "found no formatter module", "spool replay summary", every spool action, "concurrent flush suppressed", etc. is asserted

#### Scenario: nf-json-logger-structured-fields
- **WHEN** success, failure, spool, exception, and reporter paths are exercised with --logger json
- **THEN** json.loads on the emitted lines shows the expected keys (event_host_name, event_service_name, msg.status, msg.spooled, msg.exception.trace, msg.forwarder_name, msg.split_count, msg.attempt, ...)

#### Scenario: discard-downtimeend-silent
- **WHEN** NOTIFICATIONTYPE=DOWNTIMEEND and discard() is called (default silently=True)
- **THEN** no log line and no forward occur

#### Scenario: discard-downtimecancelled-loud
- **WHEN** DOWNTIMECANCELLED and discard(silently=False) is called
- **THEN** a discard log line is present

#### Scenario: discard-no-summary-dumps-raw
- **WHEN** a loud discard occurs without a summary
- **THEN** the raw event is dumped to the log

#### Scenario: alertmanager-empty-alerts-discard
- **WHEN** the alerts list is empty for the alertmanager_servicenow formatter
- **THEN** a silent discard occurs and no webhook POST is attempted

#### Scenario: alertmanager-payload-as-string
- **WHEN** alertmanager_payload arrives as a string
- **THEN** ast.literal_eval path works and processing continues

#### Scenario: alertmanager-missing-node-fallback-pod
- **WHEN** no node label is present
- **THEN** pod is used as the node source

#### Scenario: alertmanager-missing-node-fallback-instance
- **WHEN** neither node nor pod is present
- **THEN** instance is used

#### Scenario: alertmanager-missing-node-placeholder
- **WHEN** none of node/pod/instance are present
- **THEN** a placeholder string is used

#### Scenario: alertmanager-firing-vs-resolved-status
- **WHEN** an alert status of firing vs resolved is seen
- **THEN** it is mapped into the record severity field

#### Scenario: naemonlog-reporter-missing-command-file
- **WHEN** no command_file is configured and no naemon.cfg can be read
- **THEN** report_event completes without exception (silent no-op)

#### Scenario: naemonlog-reporter-api-cmd-write
- **WHEN** an explicit command_file is supplied
- **THEN** a [timestamp] LOG;... line is appended

#### Scenario: naemonlog-reporter-default-contactname
- **WHEN** CONTACTNAME is missing
- **THEN** GLOBAL is used as the default

#### Scenario: naemonlog-reporter-default-notificationcommand
- **WHEN** host vs service events are reported without NOTIFICATIONCOMMAND
- **THEN** the host vs service default command name is derived correctly

#### Scenario: reporter-instantiation-failure
- **WHEN** an unknown reporter name is supplied
- **THEN** a critical log is emitted but the forwarding outcome is unaffected

#### Scenario: naemonlog-reporter-no-config-anywhere
- **WHEN** report_event is called with neither command_file in reporter_opts nor a readable $OMD_ROOT/tmp/naemon/naemon.cfg
- **THEN** the method completes with no exception and writes nothing (pure silent no-op path)

#### Scenario: oauth2-concurrent-token-lock
- **WHEN** two parallel acquire_token() calls occur
- **THEN** the token endpoint is contacted only once

#### Scenario: oauth2-token-scope-in-request
- **WHEN** token_scope is set on the forwarder
- **THEN** the scope field is present in the token POST body

#### Scenario: oauth2-insecure-applies-to-token-endpoint
- **WHEN** insecure=no
- **THEN** the token POST uses verify=True

#### Scenario: oauth2-api-failure-after-valid-token
- **WHEN** the API returns 401 after a valid cached token
- **THEN** submit_one returns False, the event is spooled, and the cache file is retained

#### Scenario: oauth2-token-response-missing-access-token
- **WHEN** the token JSON is malformed (no access_token)
- **THEN** a critical log is emitted and no cache write occurs

#### Scenario: oauth2-logger-sync-to-webhook-module
- **WHEN** the oauth2 forwarder initializes
- **THEN** _webhook_module.logger is set before delegating to super().submit_one()

#### Scenario: oauth2-token-response-no-expires-in
- **WHEN** the token endpoint response omits "expires_in"
- **THEN** the code defaults to 3600 and the resulting cache entry has a correct expires_at computed from time.time() + 3600

#### Scenario: readme-formatter-class-naming
- **WHEN** --forwarder foo is used
- **THEN** FooFormatter and FooForwarder are loaded per the documented naming rule

#### Scenario: readme-discard-api
- **WHEN** discard() and discard(silently=False) are exercised as shown in README examples
- **THEN** the documented behaviors (silent vs loud, no forward) are observed

#### Scenario: readme-max-spool-minutes-default
- **WHEN** forwarderopt omits max_spool_minutes
- **THEN** the default of 5 minutes is honored

#### Scenario: readme-logfile-backups-default
- **WHEN** forwarderopt omits logfile_backups
- **THEN** the default of 3 backups is honored

#### Scenario: own-module-contract-smokes-exist
- **WHEN** the contracts layer files (or their smoke companions) are read
- **THEN** there exist a small number of tiny, heavily-commented own-module smokes (more than 6 allowed) for formatter, forwarder (nf), decider, runner (eh), and cross-handoff that use the exact same entry points and fixtures as user code and are suitable as direct templates for an agent implementing a new external integration. Builtin naemonlog reporter coverage exists; no dedicated "own reporter" smoke is required.

#### Scenario: eh-runner-returns-false
- **WHEN** a runner's run() returns False
- **THEN** critical "run failed" is logged and no forwarder handoff occurs

#### Scenario: eh-runner-returns-none
- **WHEN** run() returns None
- **THEN** the intentional abort path is taken and the appropriate log is emitted

#### Scenario: eh-runner-subprocess-timeout
- **WHEN** a built-in runner's subprocess exceeds its timeout
- **THEN** ForwarderTimeoutError (or equivalent) is logged

#### Scenario: eh-concurrent-handle-subprocess
- **WHEN** two simultaneous CLI invocations of eventhandler occur for the same tag
- **THEN** the second is suppressed (extend unit test coverage to the subprocess case)

#### Scenario: eh-default-decider-soft-state-type
- **WHEN** SERVICESTATETYPE=SOFT with attempt 1 is seen by the default decider
- **THEN** the runner is triggered (documented default behavior)

#### Scenario: eh-runneropt-precedence-chain
- **WHEN** the same attribute is supplied at __init__ default, runneropt, and event.payload levels
- **THEN** the precedence is __init__ < runneropt < payload

#### Scenario: eh-forwarder-not-configured
- **WHEN** no --forwarder is supplied to eventhandler and the runner succeeds
- **THEN** no notification attempt is made

#### Scenario: eh-forwarder-handoff-payload-shape
- **WHEN** a runner result is handed off
- **THEN** the forwarded event contains NOTIFICATIONTYPE=EVENTHANDLER, author from runnertag, and the host/service macros

#### Scenario: eh-json-logger-run-failure
- **WHEN** a runner fails with --logger json active
- **THEN** the JSON log contains failure status

#### Scenario: eh-enrich-adds-omd-metadata
- **WHEN** a raw event is passed to handle()
- **THEN** omd_site, omd_originating_host, omd_originating_fqdn, and omd_originating_timestamp are injected (mirrors nf enrich_raw_event)

#### Scenario: eh-validate-decided-incomplete-aborts
- **WHEN** the decider produces a DecidedEvent with payload but no summary (or vice versa)
- **THEN** critical "a decided event ... must have the attributes payload and summary" is logged and the runner does not execute

#### Scenario: eh-discard-loud-during-handle
- **WHEN** the decider calls discard(silently=False) during handle()
- **THEN** a loud "discarded: ..." log appears, no runner is invoked, and no forwarder handoff occurs

#### Scenario: nf-bin-help-exits-zero
- **WHEN** notificationforwarder --help is invoked
- **THEN** exit code is 0

#### Scenario: eh-bin-help-exits-zero
- **WHEN** eventhandler --help is invoked
- **THEN** exit code is 0

#### Scenario: nf-bin-missing-required-args
- **WHEN** notificationforwarder is invoked without a forwarder argument
- **THEN** a non-zero exit occurs with an actionable message

#### Scenario: eh-bin-missing-required-args
- **WHEN** eventhandler is invoked without a runner argument
- **THEN** a non-zero exit occurs with an actionable message
