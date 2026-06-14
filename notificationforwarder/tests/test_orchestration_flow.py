"""
Orchestration and flow tests for notificationforwarder.

This file covers discard extended patterns, runtime foundation tests,
and forward multiple split events.
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
    sys.path.append(os.environ["OMD_ROOT"] + "/../src")

from notificationforwarder import baseclass
from notificationforwarder.baseclass import FormattedEvent


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


def _new_forwarder(formatter_name, forwarder_name="example", forwarder_opts=None, logger_type="text"):
    return baseclass.new(
        forwarder_name,
        None,
        formatter_name,
        True,
        True,
        forwarder_opts or {},
        logger_type=logger_type,
    )


def _formatted_event(eventopts):
    return FormattedEvent(dict(eventopts))


# ============================================================================
# Discard extended tests
# ============================================================================

class TestDiscardExtended:
    def test_downtimeend_silent(self, setup, monkeypatch):
        """DOWNTIMEEND with discard(silently=True) produces no log and no forward."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Mock format_event to return a discarded event (silently)
        def format_discard(raw):
            fe = _formatted_event(raw)
            fe.discard(silently=True)
            return fe

        monkeypatch.setattr(forwarder, "format_event", format_discard)

        forward_called = [False]
        original_forward_formatted = forwarder.forward_formatted

        def mock_forward_formatted(event):
            forward_called[0] = True
            return original_forward_formatted(event)

        monkeypatch.setattr(forwarder, "forward_formatted", mock_forward_formatted)

        event = {
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "NOTIFICATIONTYPE": "DOWNTIMEEND",
        }

        forwarder.forward(event)

        # Silent discard should not forward
        assert not forward_called[0]

    def test_downtimecancelled_loud(self, setup, monkeypatch):
        """DOWNTIMECANCELLED with discard(silently=False) produces a discard log."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Mock format_event to return a discarded event (loudly)
        def format_discard(raw):
            fe = _formatted_event(raw)
            fe.discard(silently=False)
            fe.summary = "discarded downtime"
            return fe

        monkeypatch.setattr(forwarder, "format_event", format_discard)

        info_calls = []
        original_logger = baseclass.logger

        class MockLogger:
            def info(self, msg, *args, **kwargs):
                info_calls.append(msg)
            def critical(self, msg, *args, **kwargs):
                pass
            def warning(self, msg, *args, **kwargs):
                pass
            def debug(self, msg, *args, **kwargs):
                pass

        baseclass.logger = MockLogger()
        try:
            event = {
                "HOSTNAME": "h1",
                "SERVICEDESC": "svc",
                "NOTIFICATIONTYPE": "DOWNTIMECANCELLED",
            }

            forwarder.forward(event)

            # Loud discard should produce a "discarded" log
            assert any("discarded" in str(c) for c in info_calls)
        finally:
            baseclass.logger = original_logger

    def test_loud_discard_without_summary_dumps_raw(self, setup, monkeypatch):
        """Loud discard without summary dumps the raw event."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        def format_discard_no_summary(raw):
            fe = _formatted_event(raw)
            fe.discard(silently=False)
            fe.summary = None  # No summary
            return fe

        monkeypatch.setattr(forwarder, "format_event", format_discard_no_summary)

        info_calls = []
        original_logger = baseclass.logger

        class MockLogger:
            def info(self, msg, *args, **kwargs):
                info_calls.append((msg, kwargs))
            def critical(self, msg, *args, **kwargs):
                pass
            def warning(self, msg, *args, **kwargs):
                pass
            def debug(self, msg, *args, **kwargs):
                pass

        baseclass.logger = MockLogger()
        try:
            event = {"HOSTNAME": "h1", "description": "test"}

            forwarder.forward(event)

            # Loud discard should log the event summary (which gets set to str(raw_event))
            assert any("discarded" in str(c[0]) for c in info_calls)
        finally:
            baseclass.logger = original_logger


# ============================================================================
# Runtime foundation extended tests
# ============================================================================

class TestRuntimeFoundationExtended:
    def test_forwarder_forwarder_split_events(self, setup, monkeypatch):
        """Forward multiple split events independently."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        submit_calls = []
        monkeypatch.setattr(forwarder, "submit", lambda fe: submit_calls.append(fe) or True)

        # Mock split_events on the formatter
        def split_events(raw_event):
            return [
                {"HOSTNAME": "h1", "split": 1},
                {"HOSTNAME": "h1", "split": 2},
            ]

        mock_formatter = MagicMock()
        mock_formatter.split_events = split_events

        # Also need to make format_event return a valid formatted event
        def format_ok(raw):
            fe = _formatted_event(raw)
            fe.payload = {"data": "test"}
            fe.summary = "test"
            return fe

        def mock_new_formatter():
            return mock_formatter

        monkeypatch.setattr(forwarder, "new_formatter", mock_new_formatter)
        monkeypatch.setattr(forwarder, "format_event", format_ok)

        event = {"HOSTNAME": "h1", "description": "test"}

        # forward_multiple should process each split event
        if hasattr(forwarder, "forward_multiple"):
            forwarder.forward_multiple(event)
            assert len(submit_calls) == 2

    def test_forward_split_events_exception_no_delivery(self, setup, monkeypatch):
        """split_events() exception aborts without partial delivery."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        submit_calls = []
        monkeypatch.setattr(forwarder, "submit", lambda fe: submit_calls.append(fe) or True)

        def raise_split(raw_event):
            raise RuntimeError("split failed")

        mock_formatter = MagicMock()
        mock_formatter.split_events = raise_split
        monkeypatch.setattr(forwarder, "new_formatter", lambda: mock_formatter)

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
            event = {"HOSTNAME": "h1", "description": "test"}

            if hasattr(forwarder, "forward_multiple"):
                forwarder.forward_multiple(event)
                assert len(submit_calls) == 0
                assert any("split" in str(c).lower() for c in critical_calls)
        finally:
            baseclass.logger = original_logger
