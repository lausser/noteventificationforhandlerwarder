# Spec Delta

## MODIFIED Requirements

### Requirement: The test organization makes the uniform extension model and runtime layers visible
The system SHALL maintain its tests for all extension points (formatters, forwarders, reporters on notificationforwarder only, deciders, runners, loggers) in a flat structure with consistent layer-derived naming across the two sibling subprojects. This organization SHALL make it immediately obvious that shipped modules and user-written modules placed in local/lib/python/... are loaded and exercised through identical mechanisms (resolve_component + new()/handle() + pythonpath overrides). No empty or dummy files shall exist for concepts that do not exist in a subproject. RabbitMQ connection-cleanup regression tests are included; general RabbitMQ transport coverage is not required by this change.

#### Scenario: A contributor or agent looks for how to test a new integration
- **WHEN** the tests directory is examined
- **THEN** the layer files (test_contracts_formatters.py, test_contracts_forwarders.py, test_contracts_deciders.py, test_contracts_runners.py, etc.) plus a small set of tiny, heavily-commented own-module contract smokes are the obvious, copyable templates for testing a new formatter/forwarder (nf) or decider/runner (eh) uniformly, whether the implementation is shipped or user-provided.

### Requirement: Built-in forwarder modules without transport tests have direct submit coverage
The system SHALL provide automated tests that exercise the submit() and forward() paths of email, syslog, and telegram forwarders using mocks for their external transport libraries. RabbitMQ connection cleanup SHALL have a focused regression test without requiring a broker; general RabbitMQ transport simulation is not required by this change.

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

#### Scenario: RabbitMQ connection cleanup
- **WHEN** a RabbitMQ forwarder disconnects with an open connection
- **THEN** the connection close method is called, and an ordinary close exception remains handled without escaping
