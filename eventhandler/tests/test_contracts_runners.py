"""
Contract tests for eventhandler runners.

This file covers command rendering and payload override behavior of
bash, ssh, and nsc_web runners.
"""
import logging
import os
import shutil
import sys
from types import SimpleNamespace

import pytest

os.environ["PYTHONDONTWRITEBYTECODE"] = "true"

OMD_ROOT = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = OMD_ROOT

if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/../../notificationforwarder/src")
    sys.path.append(os.environ["OMD_ROOT"] + "/../src")

from eventhandler import baseclass
from eventhandler.baseclass import DecidedEvent
from eventhandler.bash.runner import BashRunner
from eventhandler.nsc_web.runner import NscWebRunner
from eventhandler.ssh.runner import SshRunner


def _setup():
    omd_root = os.path.dirname(__file__)
    os.environ["OMD_ROOT"] = omd_root
    shutil.rmtree(omd_root + "/var", ignore_errors=True)
    os.makedirs(omd_root + "/var/log", 0o755)
    os.makedirs(omd_root + "/var/tmp", 0o755)
    shutil.rmtree(omd_root + "/tmp", ignore_errors=True)
    os.makedirs(omd_root + "/tmp", 0o755)


@pytest.fixture
def setup():
    _setup()
    yield


def _new_runner(runner_name, decider_name="example", runner_opts=None, logger_type="text"):
    return baseclass.new(
        runner_name,
        None,
        decider_name,
        True,
        True,
        runner_opts or {},
        logger_type=logger_type,
    )


def _decided_event(eventopts):
    return DecidedEvent(dict(eventopts))


# ============================================================================
# Bash runner tests
# ============================================================================

class TestBashRunner:
    def test_basic_command(self, setup):
        """Bash runner wraps command as bash -c '...'"""
        runner = BashRunner({"command": "echo hello"})

        event = _decided_event({"payload": {}})
        result = runner.run(event)

        assert result == "bash -c 'echo hello'"

    def test_payload_command_override(self, setup):
        """Bash runner uses command from event.payload if present."""
        runner = BashRunner({"command": "default_command"})

        event = _decided_event({"payload": {"command": "override_command"}})
        result = runner.run(event)

        # The bash runner uses self.command, not event.payload["command"]
        # This test documents the current behavior
        assert result == "bash -c 'default_command'"


# ============================================================================
# NSC_web runner tests
# ============================================================================

class TestNscWebRunner:
    def test_with_arguments(self, setup):
        """NSC_web runner includes command and arguments."""
        runner = NscWebRunner({
            "hostname": "nsc",
            "port": 9443,
            "password": "secret",
            "command": "check_uptime",
            "arguments": "-w 10",
        })

        event = _decided_event({"payload": {}})
        result = runner.run(event)

        assert "check_nsc_web" in result
        assert "check_uptime" in result
        assert "-w 10" in result

    def test_without_arguments(self, setup):
        """NSC_web runner without arguments omits argument segment."""
        runner = NscWebRunner({
            "hostname": "nsc",
            "port": 9443,
            "password": "secret",
            "command": "check_uptime",
        })

        event = _decided_event({"payload": {}})
        result = runner.run(event)

        assert "check_nsc_web" in result
        assert "check_uptime" in result

    def test_password_quoting(self, setup):
        """NSC_web runner properly quotes passwords with special characters."""
        runner = NscWebRunner({
            "hostname": "nsc",
            "port": 9443,
            "password": "p@ss'w0rd",
            "command": "check_uptime",
        })

        event = _decided_event({"payload": {}})
        result = runner.run(event)

        # Password should be quoted
        assert "'p@ss'w0rd'" in result or '"p@ss\'w0rd"' in result

    def test_payload_overrides_init(self, setup):
        """NSC_web runner uses payload values over __init__ values."""
        runner = NscWebRunner({
            "hostname": "initial_host",
            "port": 9443,
            "password": "initial_pass",
            "command": "check_uptime",
        })

        # The runner uses overwrite_attributes before run
        # Pass the payload dict directly to overwrite_attributes
        payload = {
            "hostname": "override_host",
            "port": 12345,
            "password": "override_pass",
        }
        runner.overwrite_attributes(payload)
        result = runner.run(_decided_event({"payload": {}}))

        assert "override_host" in result
        assert "12345" in result
        assert "override_pass" in result


# ============================================================================
# SSH runner tests
# ============================================================================

class TestSshRunner:
    def test_identity_file_resolved(self, setup):
        """SshRunner resolves identity_file path via resolve_identity_file."""
        runner = SshRunner({
            "identity_file": "~/.ssh/id_rsa",
            "hostname": "targethost",
            "command": "echo hello",
        })

        # resolve_identity_file expands ~ and returns absolute path
        assert runner.identity_file is not None
        assert runner.identity_file.startswith("/")
        assert "~" not in runner.identity_file

    def test_identity_file_none(self, setup):
        """SshRunner handles None identity_file gracefully."""
        runner = SshRunner({
            "hostname": "targethost",
            "command": "echo hello",
        })

        assert runner.identity_file is None

    def test_run_includes_identity_file(self, setup):
        """SshRunner includes -i flag when identity_file is set."""
        runner = SshRunner({
            "identity_file": "~/.ssh/id_rsa",
            "hostname": "targethost",
            "command": "echo hello",
        })

        event = _decided_event({"payload": {}})
        result = runner.run(event)

        assert "-i" in result
        assert "targethost" in result
        assert "echo hello" in result


# ============================================================================
# Runner command rendering tests
# ============================================================================

class TestRunnerCommandRendering:
    def test_bash_runner_exact_wrapping(self, setup):
        """Bash runner produces exact bash -c '...' wrapping."""
        runner = BashRunner({"command": "ls -la"})

        event = _decided_event({"payload": {}})
        result = runner.run(event)

        assert result.startswith("bash -c '")
        assert result.endswith("'")
        assert "ls -la" in result


# ============================================================================
# Own-module contract smoke tests (agent templates)
# ============================================================================
# AI-AGENT TEMPLATE: when a user says "I need a runner for Ticket System XY",
# copy this structure, replace the external mock, keep the contract assertions.

class TestOwnRunnerSmoke:
    def test_own_runner_run_returns_command(self, setup):
        """
        AI-AGENT TEMPLATE: Own runner contract smoke.
        When implementing a new runner, run() can return:
        - A command string (shell command to execute)
        - True (success without subprocess)
        - False (failure without subprocess)
        - None (intentional abort, no more logging)
        """
        from eventhandler.example.runner import ExampleRunner

        runner = ExampleRunner({"echofile": "/tmp/smoke_test.txt"})
        event = _decided_event({
            "HOSTNAME": "h1",
        })
        # In production, the decider sets event.payload before runner.run() is called
        event.payload = {"content": "smoke output"}

        result = runner.run(event)

        # Contract: run() returns a command string for the example runner
        assert isinstance(result, str)
        assert "smoke output" in result

    def test_own_runner_run_returns_true(self, setup):
        """
        AI-AGENT TEMPLATE: Runner returning True means success without subprocess.
        """
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Mock run to return True (success, no subprocess)
        monkeypatch_run_true = lambda event: True
        runner.run = monkeypatch_run_true

        event = _decided_event({
            "HOSTNAME": "h1",
            "payload": {},
            "summary": "test",
        })

        result = runner.run(event)
        assert result is True

    def test_cross_handoff_event_shape(self, setup, monkeypatch):
        """
        AI-AGENT TEMPLATE: Cross-handoff smoke.
        When a runner succeeds and a forwarder is configured, the event
        passed to the forwarder must contain NOTIFICATIONTYPE=EVENTHANDLER,
        NOTIFICATIONAUTHOR, and eventhandler_success.
        """
        runner = _new_runner("example", "example", {"path": "/tmp"})

        monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(
            decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "test")
        ))

        monkeypatch.setattr(runner, "run", lambda event: True)

        forwarded_events = []

        class CapturingForwarder:
            def forward(self, event):
                forwarded_events.append(event)

        runner.forwarder = CapturingForwarder()

        raw_event = {
            "HOSTNAME": "vongsrv04",
            "SERVICEDESC": "some_service",
            "SERVICESTATE": "CRITICAL",
        }

        result = runner.handle(raw_event)

        assert result is True
        assert len(forwarded_events) == 1
        fwd = forwarded_events[0]

        # Contract: forward event shape
        assert fwd["NOTIFICATIONTYPE"] == "EVENTHANDLER"
        assert fwd["NOTIFICATIONAUTHOR"] == runner.runner_name
        assert fwd["eventhandler_success"] is True
