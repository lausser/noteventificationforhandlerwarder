## 1. Directory Structure and Playbook

- [x] 1.1 Create `demo-setup/` directory with subdirectories: `roles/servicenow/tasks`, `roles/servicenow/files`, `roles/notificationforwarder/tasks`, `roles/notificationforwarder/files`, `roles/naemon/tasks`, `roles/naemon/files`, `roles/eventhandler/tasks`, `roles/eventhandler/files`, `scenarios/lib`
- [x] 1.2 Create `demo-setup/playbook.yml` with `localhost` connection, variable `omdsite: demo`, and the four roles in order: servicenow, notificationforwarder, naemon, eventhandler

## 2. servicenow Role — Simulator

- [x] 2.1 Create `roles/servicenow/files/local/bin/svcnowsim.py` — Bottle HTTP server on port 8081 with routes: POST `/api/now/table/incident` (returns 201 with fake sys_id+number, logs flattened payload), GET `/health` (returns 200/503 based on mode), GET `/events` (HTML table of received events), POST `/mode/<mode>` (sets mode, returns current mode). Modes: `normal`, `overloaded` (503), `flaky` (random 201/503), `slow` (5-15s delay)
- [x] 2.2 Create `roles/servicenow/files/etc/init.d/servicenow` — OMD init script following hookalertnow pattern (PIDFILE `tmp/run/servicenow.pid`, using `__generic_init`)
- [x] 2.3 Create `roles/servicenow/tasks/main.yml` — copy svcnowsim.py to `local/bin/`, copy init script to `etc/init.d/`, create rc symlink at `etc/rc.d/84-servicenow`, set env var `SERVICENOW_SIM_URL=http://127.0.0.1:8081` via blockinfile

## 3. notificationforwarder Role — Plugins and Configuration

- [x] 3.1 Copy `simulation/roles/hookalertnow/files/local/lib/python/notificationforwarder/naenonow/formatter.py` to `roles/notificationforwarder/files/local/lib/python/notificationforwarder/naenonow/formatter.py`
- [x] 3.2 Create `roles/notificationforwarder/files/local/lib/python/notificationforwarder/naenonow/forwarder.py` — copy of `notificationforwarder/src/notificationforwarder/webhook/forwarder.py` with added `probe()` method that GETs `/health` (derived by replacing `/api/now/table/incident` with `/health` in `self.url`), returns True on 200, False otherwise, 3-second timeout
- [x] 3.3 Create `roles/notificationforwarder/tasks/main.yml` — create `local/lib/python/notificationforwarder/naenonow/` directory, copy formatter.py and forwarder.py, set `NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES=10` via blockinfile

## 4. naemon Role — Host, Services, Contacts, Commands

- [x] 4.1 Create `roles/naemon/files/etc/naemon/conf.d/firma/demo/custom/host.cfg` — define host `srvblub` with address `127.0.0.1`, check_command `check-host-alive`
- [x] 4.2 Create `roles/naemon/files/etc/naemon/conf.d/firma/demo/custom/service.cfg` — define service `tickettriggerer` on `srvblub` using `check_logfiles` monitoring `/tmp/level` with warning/critical patterns, 1-minute check interval, 3 max check attempts, contacts `servicenow`, same notification options as existing simulation, `flap_detection_enabled 0`
- [x] 4.3 Create `roles/naemon/files/etc/naemon/conf.d/firma/demo/custom/contact.cfg` — define contact `servicenow` with service/host notification commands `notify-service-servicenow` and `notify-host-servicenow`
- [x] 4.4 Create `roles/naemon/files/etc/naemon/conf.d/firma/demo/custom/command.cfg` — define `notify-host-servicenow` and `notify-service-servicenow` commands invoking `notificationforwarder --forwarder naenonow --formatter naenonow --reporter naemonlog --forwarderopt url=http://127.0.0.1:8081/api/now/table/incident` with all relevant `--eventopt` macros (HOSTNAME, SERVICEDESC, SERVICESTATE, SERVICEOUTPUT, NOTIFICATIONTYPE, SHORTDATETIME, HOSTDOWNTIME, SERVICEDOWNTIME, etc.)
- [x] 4.5 Create `roles/naemon/tasks/main.yml` — create `etc/naemon/conf.d/firma/demo/custom/` directory, copy all four cfg files

## 5. eventhandler Role — Decider, Autoheal Service, Command

- [x] 5.1 Create `roles/eventhandler/files/local/lib/python/eventhandler/demo/decider.py` — `DemoDecider(EventhandlerDecider)` with `decide_and_prepare()` that: discards on downtime (silent), discards on OK state, discards on attempt >= 2 (not silent), and on attempt 1 builds a command string from eventopts writing to `<OMD_ROOT>/var/log/autoheal_demo.log` with `event.payload["command"]` set to an echo command containing all eventopts
- [x] 5.2 Create `roles/eventhandler/files/etc/naemon/conf.d/firma/demo/custom/autoheal_service.cfg` — define service `autoheal_test` on `srvblub` using `check_logfiles` on `/tmp/level`, 1-minute check interval, 3 max check attempts, `event_handler autoheal-handler`, contacts `servicenow`, `flap_detection_enabled 0`
- [x] 5.3 Create `roles/eventhandler/files/etc/naemon/conf.d/firma/demo/custom/autoheal_command.cfg` — define command `autoheal-handler` invoking `eventhandler --decider demo --runner bash --runneropt "command=exit 0"` with all relevant `--eventopt` macros (HOSTNAME, SERVICEDESC, SERVICESTATE, SERVICESTATETYPE, SERVICEATTEMPT, SERVICEOUTPUT, HOSTDOWNTIME, SERVICEDOWNTIME)
- [x] 5.4 Create `roles/eventhandler/tasks/main.yml` — create `local/lib/python/eventhandler/demo/` directory, copy decider.py, create naemon cfg directories, copy autoheal_service.cfg and autoheal_command.cfg

## 6. Demo Scenarios — Executable Test Scripts

- [x] 6.1 Create `scenarios/lib/scenario-setup.sh` — shell functions `scenario_setup()` (restart servicenow sim, reset mode, clear spool DB via python3, clear forwarder+autoheal logs), `assert_event_received(count)` (poll simulator `/events` up to 90s counting `<tr>` tags — **note: includes header row, off by one**), `assert_spool_count(count)` (query SQLite spool DB via python3, auto-discovers table name starting with `events_`), `assert_autoheal_log(pattern)` (grep autoheal log with timeout), `get_simulator_event_count()` (parse total from `/events` page), `trigger_seq(seq, state)` (write seq+state to `/tmp/level`), `wait_for_hard(desc, sec)` (sleep for notification), `assert_seq_in_simulator(seq)` / `assert_seq_not_in_simulator(seq)` (check seq presence in events payload), `get_discard_count()` (count dropped lines in forwarder log), `assert_forwarder_log_contains(pattern)`
- [x] 6.2 Create `scenarios/01-normal-delivery.sh` — run scenario_setup, trigger critical alert via `/tmp/level`, wait for check interval, assert_event_received 1, exit 0 on success
- [x] 6.3 Create `scenarios/02-spool-and-flush.sh` — run scenario_setup, switch sim to overloaded, trigger 3 alerts at 30s intervals (echo critical/warning/critical), assert_spool_count 3, switch sim to normal, trigger 4th alert, assert_event_received 4, verify chronological order
- [x] 6.4 Create `scenarios/03-retention-and-flush.sh` — 15-minute cycle with NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES=10 default, switch sim overloaded, trigger 5 events at 200s intervals with seq=1..5 and alternating critical/warning states, wait for HARD notification each time, verify spool DB has 10 events (5 seq × 2 services), switch sim normal, trigger seq=6, wait for HARD (probe→flush→deliver), verify seq=1,2 absent (unambiguous discard >12min), verify seq=5,6 present (unambiguous delivery <8min), verify forwarder log shows "dropped N outdated events" + "spool replay summary" with attempted+recovered+dropped, verify spool DB empty after flush
- [x] 6.5 Create `scenarios/04-eventhandler-autoheal.sh` — run scenario_setup, trigger critical alert, wait for 3 check cycles (max_check_attempts), assert_autoheal_log matches host=srvblub service=autoheal_test state=CRITICAL

## 7. Verification

- [x] 7.1 Verify `demo-setup/` directory structure matches design (playbook.yml, 4 role directories with tasks/ and files/, scenarios/ with lib/ and 4 scripts)
- [x] 7.2 Verify all Python files have valid syntax (`python3 -c "import ast; ast.parse(open(f).read())"`)
- [x] 7.3 Verify playbook YAML syntax (`ansible-playbook playbook.yml --syntax-check`)
- [x] 7.4 Verify shell scripts have valid syntax (`shellcheck scenarios/*.sh`)
- [x] 7.5 Run Ansible playbook against the live container and verify each role:
  - `ansible-playbook ... -i localhost, -c local` exits 0 ✓
  - servicenow: init script exists at `~/etc/init.d/servicenow`, `omd start servicenow` starts on port 8081 ✓
  - notificationforwarder: formatter + forwarder exist at `~/local/lib/python/notificationforwarder/naenonow/` ✓
  - naemon: `~/etc/naemon/conf.d/firma/demo/custom/host.cfg` contains srvblub, `omd restart naemon` succeeds ✓
  - eventhandler: decider exists at `~/local/lib/python/eventhandler/demo/decider.py` ✓
- [x] 7.6 Run end-to-end smoke test against the container:
  - Start simulator (`omd start servicenow`), confirm `/health` returns 200 ✓
  - Trigger alert (`echo "critical" > /tmp/level`), wait for check cycle ✓
  - Verify simulator `/events` shows the received alert ✓
  - Verify forwarder log at `~/var/log/notificationforwarder_naenonow.log` shows delivery ✓
  - Switch sim to overloaded (`curl -X POST localhost:8081/mode/overloaded`), trigger another alert ✓
  - Verify forwarder log shows spooling ✓
  - Switch sim back to normal, trigger another alert ✓ (flush triggers on next notification)
  - Verify autoheal log at `~/var/log/autoheal_demo.log` shows the eventhandler output ✓
