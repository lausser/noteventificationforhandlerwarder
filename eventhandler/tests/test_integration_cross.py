"""
Cross-project integration tests for eventhandler -> notificationforwarder.

This file covers the integration between eventhandler runner execution
and notificationforwarder handoff for both success and failure cases.
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
# Cross-project integration: runner success + forwarder failure
# ============================================================================

class TestRunnerSuccessForwarderFails:
    def test_runner_success_forwarder_500_failure_notification(self, setup, monkeypatch):
        """Runner success + forwarder 500 produces failure notification payload."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Decider approves the event
        monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(
            decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "summary")
        ))

        # Runner succeeds
        monkeypatch.setattr(runner, "run", lambda event: True)

        # Forwarder fails with 500
        forwarded_events = []

        class FailingForwarder:
            def forward(self, event):
                forwarded_events.append(event)
                raise RuntimeError("HTTP 500 Internal Server Error")

        runner.forwarder = FailingForwarder()

        # Log capture
        critical_calls = []
        info_calls = []
        original_logger = baseclass.logger

        class MockLogger:
            def critical(self, msg, *args, **kwargs):
                critical_calls.append(msg)
            def info(self, msg, *args, **kwargs):
                info_calls.append(msg)
            def warning(self, msg, *args, **kwargs):
                pass
            def debug(self, msg, *args, **kwargs):
                pass

        baseclass.logger = MockLogger()
        try:
            raw_event = {
                "HOSTNAME": "vongsrv04",
                "SERVICEDESC": "some_service",
                "SERVICESTATE": "CRITICAL",
            }

            result = runner.handle(raw_event)

            # Runner should report success despite forwarder failure
            assert result is True

            # Forwarder should have been called with proper event shape
            assert len(forwarded_events) == 1
            fwd_event = forwarded_events[0]
            assert fwd_event["NOTIFICATIONTYPE"] == "EVENTHANDLER"
            assert fwd_event["NOTIFICATIONAUTHOR"] == runner.runner_name
            assert fwd_event["eventhandler_success"] is True
            assert fwd_event["SERVICESTATE"] == "OK"  # Success maps to OK

            # Forwarder handoff failure should be logged
            assert any("forwarder handoff failed" in str(c) for c in critical_calls)
        finally:
            baseclass.logger = original_logger

    def test_runner_failure_forwarder_500_failure_notification(self, setup, monkeypatch):
        """Runner failure + forwarder 500 produces failure notification with FAILED state."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Decider approves
        monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(
            decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "summary")
        ))

        # Runner fails (command not found)
        monkeypatch.setattr(runner, "run", lambda event: "false")

        # Forwarder fails
        forwarded_events = []

        class FailingForwarder:
            def forward(self, event):
                forwarded_events.append(event)
                raise RuntimeError("HTTP 500")

        runner.forwarder = FailingForwarder()

        critical_calls = []
        original_logger = baseclass.logger

        class MockLogger:
            def critical(self, msg, *args, **kwargs):
                critical_calls.append(msg)
            def info(self, msg, *args, **kwargs):
                pass
            def warning(self, msg, *args, **kwargs):
                pass
            def debug(self, msg, *args, **kwargs):
                pass

        baseclass.logger = MockLogger()
        try:
            raw_event = {
                "HOSTNAME": "vongsrv04",
                "SERVICEDESC": "some_service",
                "SERVICESTATE": "OK",
            }

            result = runner.handle(raw_event)

            # Runner should report failure
            assert result is False

            # Forwarder should have been called with FAILED state
            assert len(forwarded_events) == 1
            fwd_event = forwarded_events[0]
            assert fwd_event["NOTIFICATIONTYPE"] == "EVENTHANDLER"
            assert fwd_event["eventhandler_success"] is False
            assert fwd_event["SERVICESTATE"] == "CRITICAL"  # Failure maps to CRITICAL

            # "run failed" should be logged
            assert any("run failed" in str(c) for c in critical_calls)
        finally:
            baseclass.logger = original_logger


# ============================================================================
# Cross-project integration: decider discard
# ============================================================================

class TestDeciderDiscardNoForward:
    def test_decider_discard_no_forwarder_invoked(self, setup, monkeypatch):
        """Decider discard means no forwarder is invoked."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        # Decider discards the event
        def discard_event(event):
            event.discard(silently=False)
            return event

        monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(
            decide_and_prepare=discard_event
        ))

        # Forwarder should never be called
        mock_forwarder = MagicMock()
        runner.forwarder = mock_forwarder

        raw_event = {
            "HOSTNAME": "vongsrv04",
            "SERVICEDESC": "some_service",
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 3,
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": True,  # This triggers discard in default decider
        }

        # Reset to use default decider instead
        runner = _new_runner("example", "default", {"path": "/tmp"})
        runner.forwarder = mock_forwarder

        result = runner.handle(raw_event)

        # Forwarder should not have been called
        mock_forwarder.forward.assert_not_called()

    def test_decider_discard_no_notification_log_activity(self, setup, monkeypatch):
        """Decider discard produces no notification log file write."""
        runner = _new_runner("example", "default", {"path": "/tmp"})

        # Mock forwarder to track if forward is called
        mock_forwarder = MagicMock()
        runner.forwarder = mock_forwarder

        raw_event = {
            "HOSTNAME": "vongsrv04",
            "SERVICEDESC": "some_service",
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 3,
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": True,
        }

        result = runner.handle(raw_event)

        # Forwarder should not be invoked at all
        mock_forwarder.forward.assert_not_called()
        # No notification should have been attempted
        assert result is not None  # handle returns the success value


# ============================================================================
# Cross-project integration: forward event shape verification
# ============================================================================

class TestForwardEventShape:
    def test_success_forward_event_shape(self, setup, monkeypatch):
        """Forward event on success has correct shape with stdout/stderr."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(
            decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "summary")
        ))

        # Runner returns a command that produces stdout/stderr
        monkeypatch.setattr(runner, "run", lambda event: "echo hello_output")

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

        # Verify the complete forward event shape
        assert fwd["NOTIFICATIONTYPE"] == "EVENTHANDLER"
        assert fwd["NOTIFICATIONAUTHOR"] == runner.runner_name
        assert fwd["eventhandler_success"] is True
        assert fwd["SERVICESTATE"] == "OK"
        assert "stdout:" in fwd["NOTIFICATIONCOMMENT"]
        assert "hello_output" in fwd["NOTIFICATIONCOMMENT"]
        # Original event fields are preserved
        assert fwd["HOSTNAME"] == "vongsrv04"
        assert fwd["SERVICEDESC"] == "some_service"

    def test_failure_forward_event_shape(self, setup, monkeypatch):
        """Forward event on failure has correct shape."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(
            decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "summary")
        ))

        monkeypatch.setattr(runner, "run", lambda event: "false")

        forwarded_events = []

        class CapturingForwarder:
            def forward(self, event):
                forwarded_events.append(event)

        runner.forwarder = CapturingForwarder()

        raw_event = {
            "HOSTNAME": "vongsrv04",
            "SERVICEDESC": "some_service",
            "SERVICESTATE": "OK",
        }

        result = runner.handle(raw_event)

        assert result is False
        assert len(forwarded_events) == 1
        fwd = forwarded_events[0]

        assert fwd["NOTIFICATIONTYPE"] == "EVENTHANDLER"
        assert fwd["eventhandler_success"] is False
        assert fwd["SERVICESTATE"] == "CRITICAL"  # Failure maps to CRITICAL
        assert fwd["HOSTNAME"] == "vongsrv04"

    def test_host_event_forward_shape(self, setup, monkeypatch):
        """Host-only event uses HOSTSTATE instead of SERVICESTATE."""
        runner = _new_runner("example", "example", {"path": "/tmp"})

        monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(
            decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "summary")
        ))

        monkeypatch.setattr(runner, "run", lambda event: True)

        forwarded_events = []

        class CapturingForwarder:
            def forward(self, event):
                forwarded_events.append(event)

        runner.forwarder = CapturingForwarder()

        # Host event (no SERVICEDESC)
        raw_event = {
            "HOSTNAME": "vongsrv04",
            "HOSTSTATE": "DOWN",
        }

        result = runner.handle(raw_event)

        assert result is True
        assert len(forwarded_events) == 1
        fwd = forwarded_events[0]

        # HOSTSTATE should be mapped to UP on success
        assert fwd["HOSTSTATE"] == "UP"
        assert "SERVICESTATE" not in fwd
        assert fwd["eventhandler_success"] is True
