## ADDED Requirements

### Requirement: Scenario 01 verifies normal delivery
A script `scenarios/01-normal-delivery.sh` SHALL set up a fresh state (clear spool DB, clear simulator event log), trigger a single critical alert via `/tmp/level`, wait for the check interval, and verify that the simulator received exactly 1 event with the correct hostname and service description.

#### Scenario: Single alert delivered
- **WHEN** `scenarios/01-normal-delivery.sh` is executed
- **THEN** it SHALL exit with code 0 on success
- **THEN** it SHALL exit with non-zero code if the event was not received within 90 seconds

### Requirement: Scenario 02 verifies spool and flush
A script `scenarios/02-spool-and-flush.sh` SHALL switch the simulator to overloaded mode, trigger 3 critical alerts at 30-second intervals, verify that 3 events are spooled, switch the simulator back to normal mode, trigger a 4th alert, and verify that all 4 events are received by the simulator in chronological order.

#### Scenario: Spool and flush cycle
- **WHEN** `scenarios/02-spool-and-flush.sh` is executed
- **THEN** it SHALL exit with code 0 on success
- **THEN** the forwarder log SHALL contain "spooled" for events 1-3
- **THEN** the simulator SHALL have received 4 events
- **THEN** the first delivered spooled event SHALL have an older timestamp than the last delivered event

### Requirement: Scenario 03 verifies retention expiry
A script `scenarios/03-retention-and-flush.sh` SHALL set `NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES=1` temporarily, switch the simulator to overloaded mode, trigger 2 events, wait 70 seconds (past retention), trigger 2 more events, switch the simulator to normal mode, trigger a 5th event, and verify that only 3 events are received (events 3, 4, 5 — events 1 and 2 expired). The forwarder log SHALL confirm the 2 expired events were discarded.

#### Scenario: Retention boundary enforced
- **WHEN** `scenarios/03-retention-and-flush.sh` is executed
- **THEN** it SHALL exit with code 0 on success
- **THEN** the simulator SHALL have received exactly 3 events
- **THEN** the forwarder log SHALL contain "discarding" for 2 events

### Requirement: Scenario 04 verifies eventhandler auto-remediation
A script `scenarios/04-eventhandler-autoheal.sh` SHALL trigger a critical alert via `/tmp/level`, wait for the check interval and `max_check_attempts`, and verify that the autoheal log contains a line with the correct host, service, and state.

#### Scenario: Eventhandler writes to autoheal log
- **WHEN** `scenarios/04-eventhandler-autoheal.sh` is executed
- **THEN** it SHALL exit with code 0 on success
- **THEN** `<OMD_ROOT>/var/log/autoheal_demo.log` SHALL contain a line matching `host=srvblub.*service=autoheal_test.*state=CRITICAL`

### Requirement: Scenario helper library
The `scenarios/lib/` directory SHALL contain reusable shell functions:
- `assert_event_received <count>` — checks that the simulator `/events` endpoint reports exactly `<count>` events, waits up to 90 seconds with polling
- `assert_spool_count <count>` — reads the SQLite spool DB and asserts the number of pending events
- `scenario_setup` — clears the spool DB, resets the simulator event log and mode, and truncates the autoheal log

#### Scenario: Helper functions available
- **WHEN** `source scenarios/lib/scenario-setup.sh` is executed
- **THEN** the functions `assert_event_received`, `assert_spool_count`, and `scenario_setup` SHALL be available
- **THEN** `scenario_setup` SHALL reset the simulator mode to `normal`
- **THEN** `scenario_setup` SHALL clear the spool database for the `naenonow` forwarder
- **THEN** `scenario_setup` SHALL clear the autoheal demo log
