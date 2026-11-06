## Why

Evaluating and demonstrating `notificationforwarder` and `eventhandler` currently requires manual setup. There is no reproducible, one-shot environment where a prospective user can see both frameworks working end-to-end — from alert trigger through notification forwarding, spool/retry, probe-based recovery, and event-handler auto-remediation. Building `demo-setup/` gives evaluators a 60-second bootstrap to a fully instrumented OMD site, plus executable scenarios that validate every key feature.

## What Changes

- New `demo-setup/` directory at the repo root containing:
  - An Ansible playbook and four roles: `servicenow`, `notificationforwarder`, `naemon`, `eventhandler`
  - An executable `scenarios/` directory with test scripts covering normal delivery, spool-and-flush, retention expiry, and eventhandler auto-remediation
- New files within the existing `notificationforwarder` subproject: a `naenonow` forwarder plugin (copy of webhook with added `probe()` method)
- New files within the existing `eventhandler` subproject: a `demo` decider plugin that constructs runner commands from eventopts
- No modifications to any existing built-in modules or existing simulation/ content

## Capabilities

### New Capabilities

- `servicenow-simulator`: A Bottle-based HTTP server that simulates the ServiceNow incident API. Supports multiple behavior modes (normal, overloaded, flaky, slow), exposes a health endpoint (used by probe), renders an event history page, and registers as an OMD daemon for `omd start/stop` control.
- `demo-notification-forwarding`: A `naenonow` formatter/forwarder plugin pair installed under the OMD site's local plugin override path. The formatter shapes Naemon macros into ServiceNow-style payloads; the forwarder mirrors the built-in webhook transport and adds a `probe()` method so the baseclass spool/flush/retention lifecycle activates.
- `demo-event-handling`: A `demo` decider plugin installed under the OMD site's local plugin override path. The decider constructs a shell command string from eventopts (HOSTNAME, SERVICEDESC, SERVICESTATE, etc.) and sets it as the runner command, enabling the bash runner to write structured event data to a log file.
- `demo-test-scenarios`: Shell-based test scripts that drive the full environment — trigger alerts via `/tmp/level`, toggle simulator failure modes via HTTP, wait for retention boundaries, and assert expected outcomes by querying the simulator event log and the SQLite spool database.

### Modified Capabilities

- None. All changes are additive (new demo plugins, new scripts, new Ansible roles).

## Impact

- New `demo-setup/` directory at repo root, not affecting existing source code
- New `notificationforwarder/src/notificationforwarder/naenonow/forwarder.py` in the notificationforwarder subproject (alongside existing `formatter.py`)
- New `eventhandler/src/eventhandler/demo/decider.py` in the eventhandler subproject
- Ansible playbook requires: target OMD site "demo" to exist, `ansible` and `python3-bottle` installed on the host
- No dependency changes to either subproject's `pyproject.toml`
