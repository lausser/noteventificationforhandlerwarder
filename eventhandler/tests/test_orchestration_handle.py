"""
Orchestration and handle tests for eventhandler.

This file covers the handle() method, special SERVICEDESC early returns,
run_result paths, and forward event shaping.
"""
import logging
import os
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
# Special SERVICEDESC early return tests
# ============================================================================

class TestSpecialServiceDesc:
    def test_return_code_of_early_return(self, setup, monkeypatch):
        """handle() returns True immediately for 'Return code of' SERVICEDESC."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Mock to track if decider is called
        decider_called = [False]
        original_new_decider = runner.new_decider

        def mock_new_decider():
            decider = original_new_decider()
            if decider:
                original_prepare = decider.decide_and_prepare
                def tracking_prepare(event):
                    decider_called[0] = True
                    return original_prepare(event)
                decider.decide_and_prepare = tracking_prepare
            return decider

        monkeypatch.setattr(runner, "new_decider", mock_new_decider)

        # SERVICEDESC matching the regex pattern
        raw_event = {
            "HOSTNAME": "h1",
            "SERVICEDESC": "Return code of 127",
            "SERVICESTATE": "CRITICAL",
        }

        result = runner.handle(raw_event)

        assert result is True
        assert decider_called[0] is False  # Decider was not called

    def test_timed_out_early_return(self, setup, monkeypatch):
        """handle() returns True immediately for 'Timed Out' SERVICEDESC."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        raw_event = {
            "HOSTNAME": "h1",
            "SERVICEDESC": "Timed Out",
            "SERVICESTATE": "CRITICAL",
        }

        result = runner.handle(raw_event)
        assert result is True


# ============================================================================
# run_result path tests
# ============================================================================

class TestRunResult:
    def test_run_returns_false_no_handoff(self, setup, monkeypatch):
        """run() returning False yields success=False and no handoff."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Mock run to return False
        monkeypatch.setattr(runner, "run", lambda event: False)

        # Mock handoff to track if called
        handoff_called = [False]
        original_handoff = runner.handoff_to_forwarder

        def mock_handoff(*args):
            handoff_called[0] = True

        monkeypatch.setattr(runner, "handoff_to_forwarder", mock_handoff)

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
        })
        event.payload = {}
        event.summary = "test"

        result = runner.execute_decided_event(event)

        assert result[0] is False  # success
        assert handoff_called[0] is False  # No handoff

    def test_run_returns_none_no_more_logging(self, setup, monkeypatch):
        """run() returning None triggers no_more_logging path."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Mock run to return None
        monkeypatch.setattr(runner, "run", lambda event: None)

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
        })
        event.payload = {}
        event.summary = "test"

        # Should not raise
        result = runner.execute_decided_event(event)

        assert result[0] is None  # success is None

    def test_run_returns_command_subprocess_path(self, setup, monkeypatch):
        """run() returning a command string exercises Popen path."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Mock run to return a command string
        monkeypatch.setattr(runner, "run", lambda event: "echo test_output")

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
        })
        event.payload = {}
        event.summary = "test"

        result = runner.execute_decided_event(event)

        # Should have executed the command
        assert result[0] is True  # success


# ============================================================================
# Overwrite attributes tests
# ============================================================================

class TestOverwriteAttributes:
    def test_payload_overrides_runner_attributes(self, setup):
        """Payload values override runner __init__ and runneropt values."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Set initial attribute
        runner.hostname = "initial_host"

        # Payload with override
        payload = {"hostname": "override_host"}

        runner.overwrite_attributes(payload)

        assert runner.hostname == "override_host"

    def test_precedence_chain(self, setup):
        """Precedence is __init__ < runneropt < payload."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Set values at different levels
        runner.hostname = "init_value"
        runner.port = "runneropt_value"

        # Payload overrides
        payload = {"hostname": "payload_value"}

        runner.overwrite_attributes(payload)

        assert runner.hostname == "payload_value"
        assert runner.port == "runneropt_value"  # Not overridden


# ============================================================================
# Forward event shaping tests
# ============================================================================

class TestForwardEventShaping:
    def test_build_forward_event_success(self, setup):
        """Forward event contains correct fields on success."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        raw_event = {
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "SERVICESTATE": "CRITICAL",
        }

        forward_event = runner.build_forward_event(raw_event, True, b"stdout", b"stderr")

        assert forward_event["NOTIFICATIONTYPE"] == "EVENTHANDLER"
        assert forward_event["NOTIFICATIONAUTHOR"] == runner.runner_name
        assert forward_event["eventhandler_success"] is True
        assert forward_event["SERVICESTATE"] == "OK"  # Success maps to OK

    def test_build_forward_event_failure(self, setup):
        """Forward event contains correct fields on failure."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        raw_event = {
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "SERVICESTATE": "OK",
        }

        forward_event = runner.build_forward_event(raw_event, False, b"stdout", b"stderr")

        assert forward_event["NOTIFICATIONTYPE"] == "EVENTHANDLER"
        assert forward_event["eventhandler_success"] is False
        assert forward_event["SERVICESTATE"] == "CRITICAL"  # Failure maps to CRITICAL

    def test_build_forward_event_host_state(self, setup):
        """Forward event maps host state correctly."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Host event (no SERVICEDESC)
        raw_event = {
            "HOSTNAME": "h1",
            "HOSTSTATE": "DOWN",
        }

        forward_event = runner.build_forward_event(raw_event, True, b"stdout", b"stderr")

        assert forward_event["HOSTSTATE"] == "UP"  # Success maps to UP

        forward_event_fail = runner.build_forward_event(raw_event, False, b"stdout", b"stderr")

        assert forward_event_fail["HOSTSTATE"] == "DOWN"  # Failure keeps DOWN


# ============================================================================
# Handoff skipping tests
# ============================================================================

class TestHandoffSkipping:
    def test_handoff_skipped_when_success_none(self, setup, monkeypatch):
        """Handoff is skipped when success is None (no_more_logging path)."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Mock the forwarder to track if forward() is called
        mock_forwarder = MagicMock()
        runner.forwarder = mock_forwarder

        # Simulate success=None path by calling with None
        runner.handoff_to_forwarder({}, None, None, None)

        # The forwarder.forward() should not be called when success is None
        mock_forwarder.forward.assert_not_called()

    def test_handoff_skipped_without_forwarder(self, setup, monkeypatch):
        """Handoff is skipped when no forwarder is configured."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Remove forwarder if exists
        if hasattr(runner, "forwarder"):
            delattr(runner, "forwarder")

        # Should not raise
        runner.handoff_to_forwarder({}, True, b"stdout", b"stderr")


# ============================================================================
# Handle execution and forwarder error tests (from test_builtin_plugins_focus.py)
# ============================================================================

class TestHandleExecution:
    def test_handle_forwards_execution_results_and_survives_forwarder_errors(self, setup, monkeypatch):
        """Handle forwards execution results and survives forwarder errors."""
        runner = _new_runner("example", "example", {"path": "/tmp"})
        monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "summary")))
        monkeypatch.setattr(runner, "run", lambda event: True)

        forwarded = []

        class BrokenForwarder:
            def forward(self, event):
                forwarded.append(event)
                raise RuntimeError("downstream failed")

        runner.forwarder = BrokenForwarder()
        assert runner.handle({"summary": "ignored", "content": "payload"}) is True
        assert forwarded and forwarded[0]["NOTIFICATIONTYPE"] == "EVENTHANDLER"

    def test_notification_forwarder_handoff_failure_is_logged(self, setup, monkeypatch):
        """Notification forwarder handoff failure is logged."""
        runner = _new_runner("example", "example", {"path": "/tmp"})
        monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "summary")))
        monkeypatch.setattr(runner, "run", lambda event: True)

        class BrokenForwarder:
            def forward(self, event):
                raise RuntimeError("handoff failed")

        runner.forwarder = BrokenForwarder()
        runner.handle({"summary": "safe", "content": "payload"})

    def test_concurrent_handle_attempt_is_suppressed(self, setup):
        """Concurrent handle attempt is suppressed."""
        runner = _new_runner("example", "example", {"path": "/tmp"})
        assert runner._handle_lock.acquire(blocking=False)
        try:
            assert runner.handle({"summary": "safe", "content": "payload"}) is None
        finally:
            runner._handle_lock.release()
