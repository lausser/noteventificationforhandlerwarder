## ADDED Requirements

### Requirement: Demo decider constructs runner command from eventopts
The `demo` decider SHALL inspect `event.eventopts` and construct a shell command string in `event.payload["command"]` that writes a structured log line to `<OMD_ROOT>/var/log/autoheal_demo.log`. The log line SHALL include HOSTNAME, SERVICEDESC, SERVICESTATE, SERVICESTATETYPE, SERVICEATTEMPT, and SERVICEOUTPUT. The decider SHALL discard events during downtime, recovery (OK state), or after the first attempt.

#### Scenario: First hard problem detected
- **WHEN** `event.eventopts` contains `SERVICESTATE=CRITICAL`, `SERVICEATTEMPT=1`, `SERVICESTATETYPE=HARD`, `HOSTNAME=srvblub`, `SERVICEDESC=autoheal_test`, `SERVICEOUTPUT="cpu overload"`
- **WHEN** `decide_and_prepare()` is called
- **THEN** `event.payload` SHALL contain key `command`
- **THEN** `event.summary` SHALL contain `srvblub`, `autoheal_test`, and `CRITICAL`
- **THEN** `event.is_discarded` SHALL be `False`

#### Scenario: Downtime discards silently
- **WHEN** `event.eventopts` contains `HOSTDOWNTIME=1`
- **WHEN** `decide_and_prepare()` is called
- **THEN** `event.is_discarded` SHALL be `True`
- **THEN** `event.is_discarded_silently` SHALL be `True`

#### Scenario: Recovery discards
- **WHEN** `event.eventopts` contains `SERVICESTATE=OK`
- **WHEN** `decide_and_prepare()` is called
- **THEN** `event.is_discarded` SHALL be `True`

#### Scenario: Second attempt discards
- **WHEN** `event.eventopts` contains `SERVICEATTEMPT=2`
- **WHEN** `decide_and_prepare()` is called
- **THEN** `event.is_discarded` SHALL be `True`
- **THEN** `event.is_discarded_silently` SHALL be `False`

### Requirement: Bash runner executes decider-built command
The eventhandler SHALL use `--runner bash` without a `--runneropt command` argument. The `demo` decider SHALL set `event.payload["command"]` to the desired shell command. The bash runner's `overwrite_attributes()` SHALL pick up the command and execute it via `subprocess.Popen`.

#### Scenario: Command written to autoheal log
- **WHEN** an eventhandler is invoked for a CRITICAL service on attempt 1
- **WHEN** the eventhandler completes
- **THEN** `<OMD_ROOT>/var/log/autoheal_demo.log` SHALL contain a line with `host=srvblub`, `service=autoheal_test`, `state=CRITICAL`, `attempt=1`

### Requirement: Autoheal service uses eventhandler
The Naemon configuration SHALL include a service `autoheal_test` on host `srvblub` that uses `check_logfiles` with the same `/tmp/level` trigger file as the notification service. The service SHALL have `event_handler` set to the `autoheal-handler` command.

#### Scenario: Service definition exists
- **WHEN** the playbook has been applied
- **THEN** `~demo/etc/naemon/conf.d/firma/demo/custom/autoheal_service.cfg` SHALL exist
- **THEN** it SHALL contain `service_description autoheal_test`
- **THEN** it SHALL contain `event_handler autoheal-handler`
- **THEN** it SHALL contain `contacts servicenow`

#### Scenario: Eventhandler command exists
- **WHEN** the playbook has been applied
- **THEN** `~demo/etc/naemon/conf.d/firma/demo/custom/autoheal_command.cfg` SHALL exist
- **THEN** it SHALL contain `command_name autoheal-handler`
- **THEN** it SHALL invoke `eventhandler` with `--decider demo --runner bash`
- **THEN** it SHALL pass `SERVICEDESC`, `SERVICESTATE`, `SERVICEATTEMPT`, `SERVICESTATETYPE`, `SERVICEOUTPUT`, `HOSTDOWNTIME`, and `SERVICEDOWNTIME` as `--eventopt` arguments
