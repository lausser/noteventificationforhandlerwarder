## ADDED Requirements

### Requirement: The test organization makes the uniform extension model and runtime layers visible
The system SHALL maintain its tests for all extension points (formatters, forwarders, reporters on notificationforwarder only, deciders, runners, loggers) in a flat structure with consistent layer-derived naming across the two sibling subprojects. This organization SHALL make it immediately obvious that shipped modules and user-written modules placed in local/lib/python/... are loaded and exercised through identical mechanisms (resolve_component + new()/handle() + pythonpath overrides). No empty or dummy files shall exist for concepts that do not exist in a subproject. RabbitMQ coverage is out of scope for this change.

#### Scenario: A contributor or agent looks for how to test a new integration
- **WHEN** the tests directory is examined
- **THEN** the layer files (test_contracts_formatters.py, test_contracts_forwarders.py, test_contracts_deciders.py, test_contracts_runners.py, etc.) plus a small set of tiny, heavily-commented own-module contract smokes are the obvious, copyable templates for testing a new formatter/forwarder (nf) or decider/runner (eh) uniformly, whether the implementation is shipped or user-provided.

### Requirement: Built-in forwarder modules without transport tests have direct submit coverage
The system SHALL provide automated tests that exercise the submit() and forward() paths of email, syslog, and telegram forwarders using mocks for their external transport libraries. (RabbitMQ is intentionally out of scope for this project; it is a legacy carry-over plugin with no relevance and requires no transport simulation or dedicated tests.)

#### Scenario: email-forwarder-smtp-success
- **WHEN** a formatter provides html + text and submit is called on EmailForwarder
- **THEN** smtplib.SMTP.sendmail is called with the correct sender, recipient, subject, and MIME parts

#### Scenario: email-forwarder-html-only-payload
- **WHEN** the payload contains html but no text
- **THEN** an HTML MIME part is attached and sent

#### Scenario: email-forwarder-text-only-payload
- **WHEN** the payload contains text but no html
- **THEN** a plain-text MIME part is attached and sent

#### Scenario: email-forwarder-missing-body-fallback
- **WHEN** the payload contains neither html nor text
- **THEN** a fallback message body containing "formatter must return html or text" is sent

#### Scenario: email-forwarder-smtp-exception
- **WHEN** SMTP raises during send
- **THEN** submit() returns False and a critical log containing "sending mail failed" is emitted

#### Scenario: email-forwarder-failure-spools
- **WHEN** forward() encounters an SMTP failure for a non-heartbeat event
- **THEN** the raw event is persisted in sqlite and logs mention "forward failed" plus the current spool queue length

#### Scenario: syslog-forwarder-udp-success
- **WHEN** a syslog forwarder with default udp settings submits a formatted event
- **THEN** SysLogHandler is instantiated and the message is logged at the configured priority with the payload text

#### Scenario: syslog-forwarder-tcp-protocol
- **WHEN** protocol=tcp is configured
- **THEN** socktype=SOCK_STREAM is passed to the SysLogHandler constructor

#### Scenario: syslog-forwarder-facility-normalization
- **WHEN** facility is set to local0 or log_local0
- **THEN** both values resolve to the same numeric facility

#### Scenario: syslog-forwarder-invalid-facility-fallback
- **WHEN** an unknown facility string is supplied
- **THEN** the forwarder falls back to LOG_DAEMON without crashing

#### Scenario: syslog-forwarder-priority-normalization
- **WHEN** priority is set to info or log_info
- **THEN** both values resolve to the same numeric priority

#### Scenario: syslog-forwarder-invalid-priority-fallback
- **WHEN** an unknown priority string is supplied
- **THEN** the forwarder falls back to LOG_INFO without crashing

#### Scenario: syslog-forwarder-submit-exception
- **WHEN** the syslog handler raises during emit
- **THEN** submit() returns False and a critical log is emitted

#### Scenario: syslog-forwarder-failure-spools
- **WHEN** forward() encounters a submit failure for a non-heartbeat event
- **THEN** the event is spooled for retry

#### Scenario: telegram-forwarder-submit-success
- **WHEN** submit_one is called with a valid bot_token and chat_id and requests.get returns 200
- **THEN** the constructed bot URL contains the chat_id and the text parameter is URL-quoted

#### Scenario: telegram-forwarder-submit-http-failure
- **WHEN** a non-200 response is received
- **THEN** submit_one() returns False

#### Scenario: telegram-forwarder-submit-timeout-status
- **WHEN** a 408 or 504 status is received
- **THEN** submit_one() returns False and a critical timeout log is emitted

#### Scenario: telegram-forwarder-list-payload-all-success
- **WHEN** submit() is called with a list of two events and both submit_one calls succeed
- **THEN** the overall submit() returns True

#### Scenario: telegram-forwarder-list-payload-partial-failure
- **WHEN** submit() is called with a list and the second item fails
- **THEN** the overall submit() returns False

#### Scenario: telegram-forwarder-heartbeat-no-spool
- **WHEN** is_heartbeat=True and submit_one fails inside forward()
- **THEN** no sqlite spool entry is created and only a warning is logged

#### Scenario: telegram-forwarder-failure-spools-non-heartbeat
- **WHEN** a normal (non-heartbeat) event fails via forward()
- **THEN** the event is spooled

#### Scenario: telegram-submit-one-actual-call-crashes
- **WHEN** submit_one (or submit of a single event) is exercised without full mocking of the requests path
- **THEN** any NameError for request_parms (and hat_id default) is observed and documented, or the underlying typos are fixed so the module is functional

### Requirement: eventhandler built-in deciders have direct boundary branch coverage
The system SHALL provide automated tests that exercise the documented discard vs proceed decisions of the default and omd_site_self_heal deciders for downtime, attempt counts, and unhandled states.

#### Scenario: default-decider-host-downtime-discard
- **WHEN** HOSTDOWNTIME=True is seen by the default decider
- **THEN** the event is discarded loudly and the summary mentions downtime

#### Scenario: default-decider-service-downtime-discard
- **WHEN** SERVICEDOWNTIME=True is seen by the default decider
- **THEN** the event is discarded loudly

#### Scenario: default-decider-attempt-2-discard
- **WHEN** SERVICEATTEMPT=2 on a non-OK service state
- **THEN** the event is discarded loudly with a summary mentioning that the restart did not help

#### Scenario: default-decider-unhandled-silent-discard
- **WHEN** SERVICEATTEMPT=3 or an unexpected state/attempt combination occurs
- **THEN** the event is discarded silently (no discard log line)

#### Scenario: default-decider-attempt-1-proceeds
- **WHEN** SERVICEATTEMPT=1, non-OK, no downtime flags
- **THEN** the event proceeds (empty payload after decide_and_prepare) and is not discarded

#### Scenario: omd-decider-host-downtime-discard
- **WHEN** HOSTDOWNTIME=True is seen by omd_site_self_heal
- **THEN** the event is discarded loudly

#### Scenario: omd-decider-service-downtime-discard
- **WHEN** SERVICEDOWNTIME=True is seen by omd_site_self_heal
- **THEN** the event is discarded loudly

#### Scenario: omd-decider-attempt-2-discard
- **WHEN** SERVICEATTEMPT=2 on a non-OK service
- **THEN** the event is discarded loudly

#### Scenario: omd-decider-unhandled-loud-discard
- **WHEN** SERVICEATTEMPT=3 is seen by omd_site_self_heal
- **THEN** the event is discarded loudly (different policy from default decider)

#### Scenario: omd-decider-attempt-1-payload
- **WHEN** SERVICEATTEMPT=1 on a healable service
- **THEN** the payload contains user=site_name and the check_omd --heal command

### Requirement: eventhandler built-in runners have direct command rendering coverage
The system SHALL provide automated tests that exercise the command construction and payload override behavior of the ssh, nsc_web, and bash runners.

#### Scenario: ssh-runner-command-minimal
- **WHEN** only hostname is supplied
- **THEN** the rendered command is "ssh host 'exit 0'" (or the configured default command)

#### Scenario: ssh-runner-command-full-options
- **WHEN** username, port, identity_file, and command are all supplied
- **THEN** all appear in the rendered command string

#### Scenario: ssh-runner-payload-overrides-runneropt
- **WHEN** event.payload contains hostname or port
- **THEN** those values override the corresponding attributes from runneropt / __init__

#### Scenario: nsc-web-runner-with-arguments
- **WHEN** command and arguments are supplied
- **THEN** both appear in the final check_nsc_web command line

#### Scenario: nsc-web-runner-without-arguments
- **WHEN** only command is supplied (no arguments)
- **THEN** no extra quoted argument segment is appended

#### Scenario: nsc-web-runner-password-quoting
- **WHEN** the password contains single quotes
- **THEN** the password is safely quoted in the final command string

#### Scenario: nsc-web-runner-payload-overrides-init
- **WHEN** the DecidedEvent payload supplies hostname/port/password
- **THEN** those values override the values set in __init__ or runneropt

#### Scenario: bash-runner-basic-command
- **WHEN** a simple command is configured
- **THEN** the rendered command is exactly wrapped as "bash -c '...'"

#### Scenario: bash-runner-payload-command-override
- **WHEN** event.payload["command"] is present
- **THEN** it overrides the default command configured on the runner

### Requirement: eventhandler core runtime baseclass paths have direct coverage
The system SHALL provide automated tests that exercise timeout decorator behavior, DecidedEvent attribute initialization, special SERVICEDESC early returns, run_result success/None/false paths, attribute overwrite from payload, forward event shaping, and handoff skipping.

#### Scenario: eh-baseclass-timeout-uses-wrong-exception
- **WHEN** the timeout decorator catches a timeout or preserved exception
- **THEN** the result list contains ForwarderTimeoutError (or the intended type) and does not incorrectly reference notificationforwarder exception types

#### Scenario: eh-decided-event-missing-heartbeat-attr
- **WHEN** a DecidedEvent is constructed
- **THEN** self._is_heartbeat is initialized so that .is_heartbeat getter and setter do not raise AttributeError (in contrast to FormattedEvent which initializes it)

#### Scenario: eh-decided-event-duplicate-is-complete
- **WHEN** is_complete() is called on a DecidedEvent
- **THEN** the method exists (even if duplicated) and returns the expected boolean for complete vs incomplete payloads

#### Scenario: eh-special-servicedesc-early-return
- **WHEN** handle() sees a SERVICEDESC matching Return code of|Timed Out|timed out|check_by_ssh:...|service check orphaned
- **THEN** handle() returns True immediately, bypassing decider and runner

#### Scenario: eh-run-returns-false-no-handoff
- **WHEN** a runner's run() returns False (not an exception)
- **THEN** run_result yields success=False, "run failed" is logged at critical, and handoff_to_forwarder is not called

#### Scenario: eh-run-result-subprocess-path
- **WHEN** run() returns a shell command string
- **THEN** the Popen/communicate/wait branch executes and stdout, stderr, and exit_code-derived success are returned correctly

#### Scenario: eh-overwrite-attributes-from-payload
- **WHEN** the DecidedEvent payload contains keys that match runner attributes
- **THEN** overwrite_attributes mutates the runner before run() and payload values win over __init__/runneropt

#### Scenario: eh-build-forward-event-shapes
- **WHEN** a runner succeeds or fails and a forwarder is configured
- **THEN** the event passed to the forwarder contains NOTIFICATIONTYPE=EVENTHANDLER, NOTIFICATIONAUTHOR=runner_name, eventhandler_success, NOTIFICATIONCOMMENT with stdout/stderr, and host/service state mapped to UP/OK or DOWN/CRITICAL

#### Scenario: eh-handoff-skipped-when-success-none
- **WHEN** run_result returns success=None (the no_more_logging intentional-abort path)
- **THEN** handoff_to_forwarder is never invoked

### Requirement: nostr forwarder gaps have direct test coverage
The system SHALL provide automated tests for the nostr forwarder and formatter scenarios required by the nostr-notificationforwarder spec but not yet covered by test_nostr.py.

#### Scenario: nostr-missing-p-tag-fails
- **WHEN** no p tag is present in the payload or forwarderopts
- **THEN** submit returns False and the error mentions the recipient

#### Scenario: nostr-missing-p-tag-spools
- **WHEN** a missing recipient causes submit_one to fail inside forward()
- **THEN** the event is spooled for retry

#### Scenario: nostr-host-only-event
- **WHEN** an event has no SERVICEDESC
- **THEN** the body uses "Service: -" and tags include host/state only

#### Scenario: nostr-alternate-field-aliases
- **WHEN** HOST, SERVICE, OUTPUT (or other documented aliases) are used instead of canonical Nagios macro names
- **THEN** the formatter still produces correct body and tags

#### Scenario: nostr-npub-normalized-to-hex
- **WHEN** a p tag value uses npub1... encoding
- **THEN** it is converted to hex before encryption

#### Scenario: nostr-secret-not-in-logs
- **WHEN** success and failure paths are exercised
- **THEN** the nsec value never appears in any log file contents

#### Scenario: nostr-relay-failure-spools
- **WHEN** a relay publish fails inside forward()
- **THEN** the event is spooled

### Requirement: Cross-subproject integration paths have direct coverage
The system SHALL provide automated tests that combine eventhandler runner execution with notificationforwarder handoff for both success and failure cases.

#### Scenario: eventhandler-runner-ok-forwarder-fails
- **WHEN** a runner succeeds but the downstream webhook returns 500
- **THEN** the failure notification payload and log contain "eventhandler ... failed"; the runner log still shows success

#### Scenario: eventhandler-discard-no-forward
- **WHEN** a decider discards the event
- **THEN** no forwarder is invoked and no notification log file activity occurs for that event

### Requirement: Built-in formatter modules have edge-input coverage
The system SHALL provide automated tests that exercise important edge inputs and variant payloads of the email, syslog, and nostr formatters beyond the happy-path scenarios.

#### Scenario: email-formatter-host-only-notification
- **WHEN** an event has no SERVICEDESC (host-only notification)
- **THEN** the host html/text templates are used and the subject is set correctly

#### Scenario: email-formatter-acknowledgement-block
- **WHEN** NOTIFICATIONTYPE=ACKNOWLEDGEMENT
- **THEN** the rendered text includes ACKAUTHOR and ACKCOMMENT

#### Scenario: email-formatter-notification-comment
- **WHEN** a non-ACK notification has NOTIFICATIONCOMMENT
- **THEN** the comment block is rendered in the output

#### Scenario: email-formatter-missing-optional-macros
- **WHEN** optional macros such as LONGSERVICEOUTPUT or CONTACTEMAIL are missing
- **THEN** the template renders without error

#### Scenario: syslog-formatter-host-event
- **WHEN** an event has no SERVICEDESC (host-only)
- **THEN** the output field is derived from host macros

#### Scenario: syslog-formatter-multiline-output
- **WHEN** SERVICEOUTPUT contains multiline text
- **THEN** the output is preserved in a single log line

#### Scenario: nostr-formatter-custom-tags-json
- **WHEN** a tags forwarderopt is provided as a JSON string
- **THEN** the parsed tags are appended to the default tags

#### Scenario: nostr-formatter-malformed-tags-ignored
- **WHEN** the tags forwarderopt contains invalid JSON
- **THEN** defaults are still applied and no crash occurs

#### Scenario: nostr-formatter-empty-field-placeholders
- **WHEN** state or output fields are missing
- **THEN** the body shows "-" placeholders

### Requirement: Webhook forwarder has extended coverage for status codes, options, and payload modes
The system SHALL provide automated tests that exercise webhook behavior beyond the basic success/failure paths, including accepted status codes, TLS verification, URL and header overrides, timeout handling, Content-Type precedence, and raw mode.

#### Scenario: webhook-accepted-created-status
- **WHEN** the endpoint returns 201 or 202
- **THEN** the submit is treated as success

#### Scenario: webhook-insecure-verify-disabled
- **WHEN** insecure=yes is configured
- **THEN** verify=False is passed to the requests call

#### Scenario: webhook-url-override-from-event
- **WHEN** the formatter sets event.forwarderopts["url"]
- **THEN** the POST is sent to the override URL instead of the configured URL

#### Scenario: webhook-headers-merge
- **WHEN** both base headers forwarderopt and per-event headers are present
- **THEN** they are merged correctly

#### Scenario: webhook-timeout-exception
- **WHEN** requests raises a timeout exception
- **THEN** submit returns False

#### Scenario: webhook-content-type-header-precedence
- **WHEN** a Content-Type header is already supplied via headers forwarderopt or event.forwarderopts["headers"]
- **THEN** it is preserved and the mode-derived default is not added or overwritten

#### Scenario: webhook-mode-raw-list-payload
- **WHEN** mode=raw with a list payload
- **THEN** json.dumps(list) is sent as the POST body
