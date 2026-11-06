## ADDED Requirements

### Requirement: naenonow forwarder has probe method
The `naenonow` forwarder plugin SHALL be a copy of the built-in `WebhookForwarder` with an added `probe()` method. The `probe()` method SHALL send a GET request to the simulator's `/health` endpoint (derived by replacing `/api/now/table/incident` with `/health` in `self.url`) and return `True` on HTTP 200, `False` on any other response or connection error. The timeout SHALL be 3 seconds.

#### Scenario: Probe succeeds when receiver is healthy
- **WHEN** the servicenow simulator is in normal mode
- **THEN** `forwarder.probe()` SHALL return `True`

#### Scenario: Probe fails when receiver is overloaded
- **WHEN** the servicenow simulator is in overloaded mode
- **THEN** `forwarder.probe()` SHALL return `False`

### Requirement: Spooling activates on probe failure
When the baseclass's `forward_formatted()` is called and `probe()` returns `False`, the event SHALL be spooled to the SQLite database. When `probe()` returns `True`, spooled events SHALL be flushed in FIFO order before delivering the current event.

#### Scenario: Event spooled when receiver is down
- **WHEN** the simulator is in overloaded mode
- **WHEN** an alert triggers a notification
- **THEN** the event SHALL be written to the SQLite spool database
- **THEN** the forwarder log SHALL contain "spooled" for this event

#### Scenario: Flush on recovery
- **WHEN** 3 events have been spooled (simulator in overloaded mode)
- **WHEN** the simulator is returned to normal mode
- **WHEN** a new alert triggers a notification (probe succeeds, flush runs)
- **THEN** all 3 spooled events SHALL be delivered to the simulator in chronological order
- **THEN** the 4th event SHALL also be delivered after the spooled ones
- **THEN** the SQLite spool database SHALL be empty

### Requirement: Retention expiry discards old spooled events
The forwarder SHALL discard spooled events older than `NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES` (default 10) during flush. Discarded events SHALL be logged with severity CRITICAL indicating age and retention limit.

#### Scenario: Spooled event expired
- **WHEN** an event is spooled at time T
- **WHEN** `NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES` is 10
- **WHEN** a flush occurs at time T+13
- **THEN** the event SHALL NOT be delivered to the simulator
- **THEN** the forwarder log SHALL contain "discarding" with the event age and max retention
- **THEN** the SQLite spool database SHALL NOT contain the expired event

### Requirement: Naemon commands use naenonow forwarder and formatter
The notification commands SHALL invoke `notificationforwarder` with `--forwarder naenonow` and `--formatter naenonow`, with the URL hardcoded to `http://127.0.0.1:8081/api/now/table/incident`. The reporter SHALL be `naemonlog`. All relevant Naemon macros SHALL be passed as `--eventopt` arguments.

#### Scenario: Host notification command
- **WHEN** `notify-host-servicenow` is executed
- **THEN** it SHALL include `--forwarder naenonow --formatter naenonow --reporter naemonlog` and the URL pointing to the simulator

#### Scenario: Service notification command
- **WHEN** `notify-service-servicenow` is executed
- **THEN** it SHALL include the same forwarder/formatter/reporter settings plus `SERVICEDESC`, `SERVICESTATE`, and other service-specific macros

### Requirement: Environment variable controls spool retention
The Ansible `notificationforwarder` role SHALL set `NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES=10` in the OMD site's `etc/environment` file.

#### Scenario: Retention configured
- **WHEN** the playbook has been applied
- **THEN** `~demo/etc/environment` SHALL contain `NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES=10`
