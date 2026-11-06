## Context

The `simulation/` directory already exists and demonstrates a Prometheus→Alertmanager→hookalertnow→ServiceNow pipeline with a real ServiceNow API integration. It does not cover:

- The `notificationforwarder` spool/flush/retention lifecycle (probe → flush expired → deliver spooled → submit new)
- The `eventhandler` decider+runner pipeline at all
- A controllable receiver that can simulate failures for testing

`demo-setup/` fills these gaps with a self-contained Ansible-deployed OMD site that a prospective user can bootstrap in 60 seconds and then run through executable test scenarios.

## Goals / Non-Goals

**Goals:**

- One-shot Ansible playbook that fully instruments an OMD site `demo` with four roles
- A servicenow simulator that can be toggled between normal/failure modes via HTTP
- A `naenonow` forwarder with `probe()` so the baseclass spool/flush lifecycle activates
- A `demo` decider that constructs runner commands from eventopts
- Naemon host + service configs that trigger both notification forwarding and event handler flows
- Executable scenarios that validate normal delivery, spool+flush, retention expiry, and eventhandler auto-remediation
- All plugins installed under the OMD site's local override path (`~demo/local/lib/python/`), leaving built-in modules untouched

**Non-Goals:**

- Integration with real ServiceNow or any external system
- Prometheus or Alertmanager setup (covered by `simulation/`)
- Production hardening of the simulator
- CI integration of scenarios (manual/in-person demo focus)

## Architecture

### Four-Role Playbook

```
playbook.yml
├── role: servicenow              ← simulator daemon + init script + env
├── role: notificationforwarder   ← formatter + forwarder plugins + env
├── role: naemon                  ← host + services + contacts + commands
└── role: eventhandler            ← decider plugin + autoheal service + command
```

Roles are applied sequentially; no role depends on files created by another role (each creates its own directories). All converge on the same OMD site path.

### Data Flow

```
User triggers:  echo "critical" > /tmp/level
                      │
                      ▼
              ┌───────────────┐
              │   check_logfiles  │   ← Naemon check interval 1min
              └───────┬───────┘
                      │ HARD state change
          ┌───────────┴───────────┐
          ▼                       ▼
  Notification Path          Event Handler Path
  ┌─────────────────┐       ┌──────────────────────┐
  │ contact          │       │ event_handler         │
  │ servicenow       │       │ autoheal-handler      │
  └────────┬────────┘       └──────────┬───────────┘
           ▼                           ▼
  ┌─────────────────────┐   ┌───────────────────────┐
  │ notificationforwarder│   │ eventhandler           │
  │ --forwarder naenonow │   │ --decider demo         │
  │ --formatter naenonow │   │ --runner bash          │
  │ --reporter naemonlog │   └──────────┬────────────┘
  └──────────┬──────────┘              │
             ▼                         ▼
  ┌─────────────────────┐   ┌───────────────────────┐
  │ naenonow forwarder  │   │ demo decider builds   │
  │ POST + probe()      │   │ command from eventopts│
  └──────────┬──────────┘   │ bash runner executes  │
             │              │ → writes autoheal.log │
             ▼              └───────────────────────┘
  ┌──────────────────┐
  │ svcnowsim:8081    │   ← togglable: normal/overloaded/slow
  │ /api/now/table/   │
  │   /incident       │
  │ /health           │   ← probe target
  │ /events           │   ← visual history
  │ /mode/<mode>      │   ← failure injection
  └──────────────────┘
```

## Decisions

### Decision 1: Simulator as Bottle standalone, not CGI

The existing `hookalertnow.py` runs as a Waitress WSGI server on port 8080 behind Apache mod_proxy. For the simulator, we use Bottle's built-in wsgiref server directly — no Apache dependency. The init script matches the OMD daemon pattern (`etc/init.d/servicenow`, `PIDFILE: tmp/run/servicenow.pid`).

**Why not CGI?** The simulator needs HTTP mode-switching endpoints (POST /mode/...). CGI would require Apache config changes. A standalone server on 8081 is simpler and keeps the servicenow role self-contained.

### Decision 2: `naenonow` forwarder copies webhook + adds probe()

The forwarder lives at `~demo/local/lib/python/notificationforwarder/naenonow/forwarder.py`, which overrides the built-in OMD path `~demo/lib/python/notificationforwarder/naenonow/forwarder.py` (if it existed). The formatter is at the same module path.

```
naenonow/
  formatter.py    ← from simulation/ (unchanged)
  forwarder.py    ← copy of webhook/forwarder.py + probe()
```

The `probe()` method does a GET to the simulator's `/health` endpoint (derived by replacing `/api/now/table/incident` with `/health` in the URL). The baseclass `forward_formatted()` calls `probe()` before `flush()` — if probe succeeds, spooled events are delivered; if not, the current event is spooled.

**Why not override the built-in webhook forwarder?** Overriding `~demo/local/lib/python/notificationforwarder/webhook/forwarder.py` would change behavior for any config using `--forwarder webhook`, which is surprising. A new plugin `naenonow` is explicit and self-documenting.

### Decision 3: Custom `demo` decider constructs command from eventopts

The built-in `DefaultDecider` sets `event.payload = {}` (empty payload for attempt 1). The `demo` decider instead fills `event.payload["command"]` with a shell command that interpolates eventopts:

```python
class DemoDecider(EventhandlerDecider):
    def decide_and_prepare(self, event):
        if downtime or OK: discard()
        logline = f"{host}/{service} attempt={attempt} state={state} ..."
        event.payload = {"command": f"echo '{logline}' >> {logfile}"}
        event.summary = logline
```

The bash runner's `overwrite_attributes()` catches `payload["command"]` and sets `self.command`. The runner then executes `bash -c '<command>'`.

**Why not use the DefaultDecider plus a wrapper script?** The bash runner gets a static command string — it cannot reference eventopts. The decider is the only plugin that has access to eventopts at decision time. Building the command there is the simplest path.

### Decision 4: Simulator failure modes via HTTP

| Mode | POST endpoint | Behavior |
|------|--------------|----------|
| `normal` | `/mode/normal` | Returns 201 with `{"result": {"sys_id": "<uuid>", "number": "INC<counter>"}}` |
| `overloaded` | `/mode/overloaded` | Returns 503 `{"error": "Service Unavailable"}` |
| `flaky` | `/mode/flaky` | Random 201/503, 50% each |
| `slow` | `/mode/slow` | Sleeps 5-15s then returns 201 |
| `health` | `/health` (GET) | Returns 200 if mode=normal, 503 otherwise |

The current mode is stored in memory (simple class attribute) — no filesystem state needed.

### Decision 5: Spool retention boundary at 10 minutes

`NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES=10` in `~demo/etc/environment`. The spool retention scenario (scenario 03) runs as a 15-minute cycle:

1. Setup: scenario_setup restarts sim, clears all state
2. Simulator set to `overloaded` mode
3. 5 events triggered at 200s intervals with alternating states (critical/warning/critical/warning/critical), each identified by `seq=N` in the check output. Every state change causes a HARD notification after ~3 min (3 check cycles at 1-min intervals).
4. During overload, all 10 notifications (5 seq × 2 services) are spooled to SQLite
5. After 15 min, simulator set to `normal`, seq=6 triggered
6. seq=6 goes HARD → `probe()` succeeds → `flush()` runs
7. Events younger than 10 min are delivered to sim, older events are dropped
8. seq=1,2 unambiguous (>12 min) → discarded; seq=5,6 unambiguous (<8 min) → delivered; seq=3,4 at boundary → behavior depends on exact timing

Additional design decisions discovered during implementation:
- **Flap detection disabled**: Naemon's flap detection (default 20% threshold) suppresses notifications when state changes frequently. Both service definitions include `flap_detection_enabled 0`.
- **Python3-based DB queries**: `sqlite3` CLI command is not available in the container; all spool DB queries use `python3 -c` with the `sqlite3` module instead.
- **Simulator restart**: `scenario_setup()` restarts the servicenow daemon via `su - demo -c "omd restart servicenow"` to clear in-memory event state between runs.

## Risks / Trade-offs

- **[Spool timing]**: The 10-minute retention demo requires actual waiting. Mitigation: scenario documentation explains the override to 1 minute for fast demos.
- **[Simulator single-process]**: Bottle's wsgiref server is single-threaded. Under rapid-fire alerting (sub-second intervals), requests can queue. Not an issue for demo alerting at 1-minute check intervals.
- **[Init script dependency]**: The servicenow init script uses `__generic_init` from OMD's `lib/omd/init_profile`, which varies slightly between OMD versions. Tested against the same OMD version as the existing hookalertnow init script.
- **[Local override confusion]**: Having `naenonow/forwarder.py` at the local path shadows any future built-in naenonow forwarder. This is intentional for the demo but should be documented in README.
- **[`demo` decider overlaps with `default` decider]**: The `demo` decider duplicates logic from `DefaultDecider` (downtime check, OK check, attempt checks). For a demo plugin this is acceptable — clarity over reuse.

## Open Questions

- Should the simulator's `/events` page be HTML (styled) or JSON? Design defaults to a simple HTML table for in-browser viewing, with a JSON endpoint for script consumption. To be confirmed during implementation.
- Where should the scenario scripts write their assertion logs? `/tmp/demo-scenario-<name>.log` avoids polluting the OMD site logs.

## Verification Environment

A Podman container with a running OMD site `demo` is available for immediate testing:

```
Container ID:  60437d8ee938
Mount point:   /mnt/noteventificationforhandlerwarder/
               maps to repo root: /home/lausser/git/noteventificationforhandlerwarder/
OMD site:      demo (running: naemon, apache, rrdcached, npcd, crontab)
```

### Verification Workflow

```
1. Create/edit files in demo-setup/roles/*/files/
2. Files appear in container at /mnt/noteventificationforhandlerwarder/demo-setup/roles/...
3. Inside container (su - demo):
     ansible-playbook /mnt/.../demo-setup/playbook.yml -i localhost, -c local
4. Verify:
     omd restart           ← pick up new naemon config
     omd start servicenow  ← start simulator
     echo "critical" > /tmp/level  ← trigger alert
     tail var/log/notificationforwarder_naenonow.log  ← verify delivery
     curl localhost:8081/events     ← verify simulator received event
     cat var/log/autoheal_demo.log  ← verify eventhandler fired
```

This eliminates guesswork — every file path, permission, and Python import can be tested against a live OMD site before committing.

### Container Commands

```bash
# Enter the container
podman exec -it 60437d8ee938 bash

# Run Ansible inside the container
su - demo
ansible-playbook /mnt/noteventificationforhandlerwarder/demo-setup/playbook.yml \
    -i localhost, -c local

# Verify site state
omd status
omd restart naemon

# Check logs
tail -f ~/var/log/notificationforwarder_naenonow.log

# Interact with simulator
curl -s localhost:8081/health
curl -s -X POST localhost:8081/mode/overloaded
curl -s localhost:8081/events

# Trigger alerts
echo "critical" > /tmp/level
echo "warning" > /tmp/level
```

### Container Lifecycle

If the container becomes corrupted or needs resetting, a fresh container
can be provided on request. The mount path and OMD site name `demo` are
stable across container rebuilds.
