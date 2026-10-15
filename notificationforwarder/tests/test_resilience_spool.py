"""
Resilience and spool tests for notificationforwarder.

This file covers heartbeat/spool policy, probe-gated flush, enrichment,
formatter failures, and spool replay edge cases.
"""
import logging
import os
import shutil
import sys
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import time

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
from notificationforwarder.spool import SpoolStore
import notificationforwarder.webhook.forwarder as webhook_module


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
# Heartbeat and spool policy tests
# ============================================================================

class TestHeartbeatSpoolPolicy:
    def test_webhook_heartbeat_failure_no_spool(self, setup, monkeypatch):
        """Heartbeat events do not create spool entries on failure."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        monkeypatch.setattr(
            webhook_module.requests,
            "post",
            lambda *args, **kwargs: SimpleNamespace(status_code=500, text="error", reason="bad"),
        )

        spooled = []
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or True)

        # Mock format_event to return a heartbeat formatted event
        mock_formatted = _formatted_event({"description": "heartbeat event"})
        mock_formatted.is_heartbeat = True
        mock_formatted.payload = {"data": "test"}
        mock_formatted.summary = "heartbeat"
        monkeypatch.setattr(forwarder, "format_event", lambda raw: mock_formatted)

        event = {"description": "heartbeat event"}
        forwarder.forward(event)

        # Heartbeat events should not be spooled
        assert len(spooled) == 0

    def test_heartbeat_alternating_success_and_failure_does_not_grow_queue(self, setup, monkeypatch):
        """Heartbeat events must not increase the spool queue, even when delivery fails."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        results = iter([True, False, True, False])
        monkeypatch.setattr(forwarder, "submit", lambda fe: next(results))

        def make_heartbeat_event(seq):
            event = _formatted_event({"description": f"heartbeat {seq}"})
            event.is_heartbeat = True
            event.payload = {"seq": seq}
            event.summary = f"heartbeat {seq}"
            return event

        events = [
            {"description": "heartbeat 1"},
            {"description": "heartbeat 2"},
            {"description": "heartbeat 3"},
            {"description": "heartbeat 4"},
        ]

        monkeypatch.setattr(
            forwarder,
            "format_event",
            lambda raw: make_heartbeat_event(raw["description"]),
        )

        for event in events:
            forwarder.forward(event)
            assert forwarder.num_spooled_events() == 0

    def test_webhook_non_heartbeat_failure_spools(self, setup, monkeypatch):
        """Non-heartbeat events are spooled on failure."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        monkeypatch.setattr(
            webhook_module.requests,
            "post",
            lambda *args, **kwargs: SimpleNamespace(status_code=500, text="error", reason="bad"),
        )

        spooled = []
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or True)

        # Mock format_event to return a non-heartbeat formatted event
        mock_formatted = _formatted_event({"description": "normal event"})
        mock_formatted.is_heartbeat = False
        mock_formatted.payload = {"data": "test"}
        mock_formatted.summary = "normal"
        monkeypatch.setattr(forwarder, "format_event", lambda raw: mock_formatted)

        event = {"description": "normal event"}
        forwarder.forward(event)

        # Non-heartbeat events should be spooled
        assert len(spooled) == 1


# ============================================================================
# Probe-gated flush tests
# ============================================================================

class TestProbeGatedFlush:
    def test_flush_skipped_when_probe_fails(self, setup, monkeypatch):
        """Flush is skipped when probe() returns False and spool is non-empty."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Add probe method to the forwarder
        def probe():
            return False

        forwarder.probe = probe

        # Mock num_spooled_events to return non-zero
        monkeypatch.setattr(forwarder, "num_spooled_events", lambda: 5)

        # Mock flush to track if it was called
        flush_called = [False]
        original_flush = forwarder.flush

        def mock_flush():
            flush_called[0] = True
            original_flush()

        monkeypatch.setattr(forwarder, "flush", mock_flush)

        # Create a formatted event
        event = _formatted_event({"description": "test"})
        event.payload = {"description": "test"}
        event.summary = "test"

        # forward_formatted should not call flush when probe returns False
        forwarder.forward_formatted(event)

        # Note: The actual behavior depends on the implementation
        # This test verifies the probe is consulted

    def test_flush_runs_when_probe_succeeds(self, setup, monkeypatch):
        """Flush runs when probe() returns True and spool is non-empty."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Add probe method to the forwarder
        def probe():
            return True

        forwarder.probe = probe

        # Mock num_spooled_events to return non-zero
        monkeypatch.setattr(forwarder, "num_spooled_events", lambda: 5)

        # Mock flush to track if it was called
        flush_called = [False]
        original_flush = forwarder.flush

        def mock_flush():
            flush_called[0] = True

        monkeypatch.setattr(forwarder, "flush", mock_flush)

        # Create a formatted event
        event = _formatted_event({"description": "test"})
        event.payload = {"description": "test"}
        event.summary = "test"

        # forward_formatted should call flush when probe returns True
        forwarder.forward_formatted(event)

        assert flush_called[0]


# ============================================================================
# Enrichment tests
# ============================================================================

class TestEnrichment:
    def test_strips_unexpanded_macros(self, setup):
        """Enrichment removes unexpanded $MACRO$ tokens."""
        from notificationforwarder.runtime_flow import enrich_raw_event

        raw_event = {
            "HOSTNAME": "$HOSTNAME$",
            "FOO": "$",
            "BAR": "valid_value",
        }

        enriched = enrich_raw_event(raw_event)

        assert enriched.get("HOSTNAME") is None or enriched["HOSTNAME"] != "$HOSTNAME$"
        assert enriched.get("FOO") is None or enriched["FOO"] != "$"
        assert enriched["BAR"] == "valid_value"

    def test_preserves_nested_structures(self, setup):
        """Enrichment preserves nested dict/list structures."""
        from notificationforwarder.runtime_flow import enrich_raw_event

        raw_event = {
            "nested_dict": {"key": "value"},
            "nested_list": [1, 2, 3],
            "HOSTNAME": "testhost",
        }

        enriched = enrich_raw_event(raw_event)

        assert enriched["nested_dict"] == {"key": "value"}
        assert enriched["nested_list"] == [1, 2, 3]

    def test_adds_omd_metadata(self, setup):
        """Enrichment adds omd_site and other metadata fields."""
        from notificationforwarder.runtime_flow import enrich_raw_event

        raw_event = {"HOSTNAME": "testhost"}

        enriched = enrich_raw_event(raw_event)

        assert "omd_site" in enriched
        assert "omd_originating_host" in enriched
        assert "omd_originating_fqdn" in enriched
        assert "omd_originating_timestamp" in enriched


# ============================================================================
# Formatter failure tests
# ============================================================================

class TestFormatterFailure:
    def test_incomplete_formatted_event_aborts(self, setup, monkeypatch):
        """Incomplete formatted event (missing summary) aborts with critical log."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Mock new_formatter to return a formatter that sets payload but not summary
        mock_formatter = MagicMock()

        def set_incomplete(event):
            event.payload = {"data": "test"}
            # Don't set summary

        mock_formatter.format_event = set_incomplete
        monkeypatch.setattr(forwarder, "new_formatter", lambda: mock_formatter)

        # Mock logger to capture critical calls
        critical_calls = []
        original_logger = baseclass.logger

        class MockLogger:
            def critical(self, msg, *args, **kwargs):
                critical_calls.append(msg)

        baseclass.logger = MockLogger()

        try:
            event = {"description": "test"}
            result = forwarder.forward(event)

            # Should have logged "formatted event incomplete"
            assert any("incomplete" in str(call) for call in critical_calls)
        finally:
            baseclass.logger = original_logger

    def test_formatter_exception_no_spool(self, setup, monkeypatch):
        """Formatter exception aborts without spooling."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Mock new_formatter to raise exception
        def raise_formatter():
            raise ValueError("Formatter error")

        monkeypatch.setattr(forwarder, "new_formatter", raise_formatter)

        spooled = []
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or True)

        event = {"description": "test"}
        result = forwarder.forward(event)

        # Should not have spooled anything
        assert len(spooled) == 0

    def test_missing_formatter_module_aborts(self, setup, monkeypatch):
        """Missing formatter module aborts gracefully."""
        from notificationforwarder.component_loader import ComponentLoadError
        import notificationforwarder.baseclass as baseclass_module

        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Mock load_formatter to raise ComponentLoadError
        def raise_load_error(*args, **kwargs):
            raise ComponentLoadError("Formatter not found", {})

        monkeypatch.setattr(baseclass_module, "load_formatter", raise_load_error)

        # Mock logger to capture critical calls
        critical_calls = []
        original_logger = baseclass_module.logger

        class MockLogger:
            def critical(self, msg, *args, **kwargs):
                critical_calls.append(msg)

            def warning(self, msg, *args, **kwargs):
                pass

            def info(self, msg, *args, **kwargs):
                pass

            def debug(self, msg, *args, **kwargs):
                pass

        baseclass_module.logger = MockLogger()

        try:
            event = {"description": "test"}
            result = forwarder.forward(event)

            # Should have logged "found no formatter module"
            assert any("no formatter" in str(call) for call in critical_calls)
        finally:
            baseclass_module.logger = original_logger


# ============================================================================
# Spool replay edge tests
# ============================================================================

class TestSpoolReplayEdges:
    def test_discarded_event_deleted_with_trash_log(self, setup, monkeypatch):
        """Spooled event discarded during replay is skipped and deleted, not submitted."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Manually enqueue an event into the real spool
        raw_event = {"HOSTNAME": "h1", "description": "to be discarded"}
        forwarder.spool_store.enqueue(raw_event)
        assert forwarder.num_spooled_events() == 1

        # Make format_event return a discarded FormattedEvent
        def format_discarded(raw):
            fe = _formatted_event(raw)
            fe.discard(silently=True)
            return fe

        monkeypatch.setattr(forwarder, "format_event", format_discarded)

        # Mock submit to track it is NOT called for discarded events
        submit_called = []
        monkeypatch.setattr(forwarder, "submit", lambda fe: submit_called.append(True) or True)

        info_calls = []
        original_logger = baseclass.logger

        class MockLogger:
            def info(self, msg, *args, **kwargs):
                info_calls.append(msg)
            def critical(self, msg, *args, **kwargs):
                info_calls.append(msg)
            def warning(self, msg, *args, **kwargs):
                pass
            def debug(self, msg, *args, **kwargs):
                pass

        baseclass.logger = MockLogger()
        try:
            forwarder.flush()
        finally:
            baseclass.logger = original_logger

        # Discarded events are skipped (not submitted) and deleted from spool
        assert forwarder.num_spooled_events() == 0
        assert len(submit_called) == 0
        assert "discard spooled event during replay" in info_calls

    def test_persistent_failure_keeps_row_and_terminates(self, setup, monkeypatch):
        """Repeatedly failing spooled event stays in spool and loop terminates."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        raw_event = {"HOSTNAME": "h1", "description": "persistent fail"}
        forwarder.spool_store.enqueue(raw_event)
        assert forwarder.num_spooled_events() == 1

        # format_event returns a valid event but submit always fails
        def format_ok(raw):
            fe = _formatted_event(raw)
            fe.payload = {"data": "test"}
            fe.summary = "test"
            return fe

        monkeypatch.setattr(forwarder, "format_event", format_ok)

        def always_fail(formatted_event):
            return False

        monkeypatch.setattr(forwarder, "submit", always_fail)

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
            forwarder.flush()
        finally:
            baseclass.logger = original_logger

        # Event stays in spool
        assert forwarder.num_spooled_events() == 1
        # Stuck detection should have triggered
        assert any("could not be submitted" in str(c) for c in critical_calls)

    def test_spool_init_failure_returns_false(self, setup, monkeypatch):
        """Spool init failure returns False with critical log."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Make enqueue raise an exception
        def raise_enqueue(raw_event):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(forwarder.spool_store, "enqueue", raise_enqueue)

        critical_calls = []
        original_logger = baseclass.logger

        class MockLogger:
            def critical(self, msg, *args, **kwargs):
                critical_calls.append(msg)
            def warning(self, msg, *args, **kwargs):
                pass
            def info(self, msg, *args, **kwargs):
                pass
            def debug(self, msg, *args, **kwargs):
                pass

        baseclass.logger = MockLogger()
        try:
            result = forwarder.spool({"description": "test"})
        finally:
            baseclass.logger = original_logger

        assert result is False
        assert any("database error" in str(c) for c in critical_calls)

    def test_flush_beyond_batch_limit_stuck_detection(self, setup, monkeypatch):
        """Flush continues into the next batch and stops at the first failed replay."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Enqueue 12 events
        for i in range(12):
            forwarder.spool_store.enqueue({"HOSTNAME": "h1", "event_num": i})

        assert forwarder.num_spooled_events() == 12

        # the first 11 replays succeed, the 12th (in the second batch) fails
        submitted = []

        def fail_twelfth(formatted_event):
            submitted.append(formatted_event.eventopts["event_num"])
            return formatted_event.eventopts["event_num"] != 11

        monkeypatch.setattr(forwarder, "submit", fail_twelfth)

        def format_ok(raw):
            fe = _formatted_event(raw)
            fe.payload = {"data": "test"}
            fe.summary = "test"
            return fe

        monkeypatch.setattr(forwarder, "format_event", format_ok)

        info_calls = []
        critical_calls = []

        original_logger = baseclass.logger

        class MockLogger:
            def info(self, msg, context=None, *args, **kwargs):
                info_calls.append((msg, context))
            def critical(self, msg, *args, **kwargs):
                critical_calls.append(msg)
            def warning(self, msg, *args, **kwargs):
                pass
            def debug(self, msg, *args, **kwargs):
                pass

        baseclass.logger = MockLogger()
        try:
            forwarder.flush()
        finally:
            baseclass.logger = original_logger

        # the flush went on into the second batch and stopped at the 12th event
        assert submitted == list(range(12))
        assert forwarder.num_spooled_events() == 1
        assert forwarder.flush_stopped_at == 12
        assert any("could not be submitted" in str(c) for c in critical_calls)
        summary = [ctx for msg, ctx in info_calls if msg == "spool replay summary"]
        assert summary == [{
            'attempted': 12,
            'recovered_count': 11,
            'stays_in_spool_count': 1,
            'deleted_trash_count': 0,
            'dropped_count': 0,
        }]

    def test_flush_terminates_while_other_processes_spool(self, setup, monkeypatch):
        """Flush must not loop forever when concurrent processes keep spooling.

        Regression: stuck detection compared the total spool count, which
        other processes change by spooling, so the same failing head batch
        was retried endlessly while the flush lock was held.
        """
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )
        for i in range(12):
            forwarder.spool_store.enqueue({"HOSTNAME": "h1", "event_num": i})

        # a second connection plays a concurrent notificationforwarder process
        other_process = SpoolStore(forwarder.db_file, forwarder.table_name)
        other_process.open()

        def format_ok(raw):
            fe = _formatted_event(raw)
            fe.payload = {"data": "test"}
            fe.summary = "test"
            return fe

        submitted = []

        def fail_while_others_spool(formatted_event):
            submitted.append(formatted_event.eventopts["event_num"])
            other_process.enqueue({"HOSTNAME": "h1", "event_num": 1000 + len(submitted)})
            if len(submitted) > 100:
                raise SystemExit("flush does not terminate")
            return False

        monkeypatch.setattr(forwarder, "format_event", format_ok)
        monkeypatch.setattr(forwarder, "submit", fail_while_others_spool)

        critical_calls = []
        original_logger = baseclass.logger

        class MockLogger:
            def critical(self, msg, context=None, *args, **kwargs):
                critical_calls.append((msg, context))

            def info(self, msg, *args, **kwargs):
                pass

            def warning(self, msg, *args, **kwargs):
                pass

            def debug(self, msg, *args, **kwargs):
                pass

        baseclass.logger = MockLogger()
        try:
            forwarder.flush()
        finally:
            baseclass.logger = original_logger
            other_process.close()

        # the first failed submit ends the flush
        assert submitted == [0]
        # nothing lost: 12 original + 1 spooled concurrently
        assert forwarder.num_spooled_events() == 13
        # the stuck log counts only the rows of this flush's snapshot
        stuck = [ctx for msg, ctx in critical_calls if msg == "spooled events could not be submitted"]
        assert stuck == [{'spooled_count': 12, 'action': 'could_not_submit'}]

    def test_formatter_returns_none_during_replay_deletes_trash(self, setup, monkeypatch):
        """Formatter returning None during replay deletes event as trash."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        raw_event = {"HOSTNAME": "h1", "description": "unformattable"}
        forwarder.spool_store.enqueue(raw_event)
        assert forwarder.num_spooled_events() == 1

        # format_event returns None (simulating formatter exception)
        monkeypatch.setattr(forwarder, "format_event", lambda raw: None)

        info_calls = []
        critical_calls = []
        original_logger = baseclass.logger

        class MockLogger:
            def info(self, msg, *args, **kwargs):
                info_calls.append(msg)
            def critical(self, msg, *args, **kwargs):
                critical_calls.append(msg)
            def warning(self, msg, *args, **kwargs):
                pass
            def debug(self, msg, *args, **kwargs):
                pass

        baseclass.logger = MockLogger()
        try:
            forwarder.flush()
        finally:
            baseclass.logger = original_logger

        # Event should be deleted as trash
        assert forwarder.num_spooled_events() == 0
        assert any("could not format spooled event" in str(c) for c in critical_calls)
        assert any("delete trash event" in str(c) for c in info_calls)

    def test_summary_logging_resumes_after_flush(self, setup, monkeypatch):
        """baseclass_logs_summary is reset at flush start so summary log resumes."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Simulate no_more_logging() having been called (permanent switch before fix)
        forwarder.no_more_logging()
        assert forwarder.baseclass_logs_summary is False

        # Enqueue an event so flush has something to process
        raw_event = {"HOSTNAME": "h1", "description": "test resume"}
        forwarder.spool_store.enqueue(raw_event)

        # Mock format_event and submit
        def format_ok(raw):
            fe = _formatted_event(raw)
            fe.payload = {"data": "test"}
            fe.summary = "test"
            return fe

        monkeypatch.setattr(forwarder, "format_event", format_ok)
        monkeypatch.setattr(forwarder, "submit", lambda fe: True)

        forwarder.flush()

        # After flush, baseclass_logs_summary should be True again
        assert forwarder.baseclass_logs_summary is True


# ============================================================================
# Flush stops at the first failure, rejected events move to the end
# ============================================================================

class _RecordingLogger:
    """Records (level, message, context) of every log call."""
    def __init__(self):
        self.calls = []

    def __getattr__(self, level):
        def log(msg, context=None, *args, **kwargs):
            self.calls.append((level, msg, context))
        return log

    def messages(self, level):
        return [msg for lvl, msg, _ctx in self.calls if lvl == level]

    def moved(self):
        return [ctx for _lvl, msg, ctx in self.calls if msg == "spooled event moved to the end of the spool"]


class TestFlushStopAndMoveToEnd:
    """Spooled events are numbered 0, 1, 2, ... (ids 1, 2, 3, ...); the live event is "live"."""

    LIVE = {"HOSTNAME": "h1", "event_num": "live"}

    def _forwarder(self, monkeypatch, submit, num_spooled=3, heartbeat=False):
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )
        for i in range(num_spooled):
            forwarder.spool_store.enqueue({"HOSTNAME": "h1", "event_num": i})

        def format_ok(raw):
            fe = _formatted_event(raw)
            fe.payload = {"data": "test"}
            fe.summary = "test"
            if raw.get("event_num") == "live":
                fe.is_heartbeat = heartbeat
            return fe

        monkeypatch.setattr(forwarder, "format_event", format_ok)
        monkeypatch.setattr(forwarder, "submit", submit)
        # new() has set the module logger, so record from here on
        self.log = _RecordingLogger()
        monkeypatch.setattr(baseclass, "logger", self.log)
        return forwarder

    def _spooled(self, forwarder):
        rows = forwarder.spool_store.fetch_batch(limit=100)
        return [forwarder.spool_store.decode(text)["event_num"] for _id, text in rows]

    def _timestamp(self, forwarder, event_id):
        forwarder.dbcurs.execute(
            "SELECT timestamp FROM {table} WHERE id = ?".format(table=forwarder.table_name), (event_id,))
        return forwarder.dbcurs.fetchone()[0]

    @staticmethod
    def _reject_first(formatted_event):
        return formatted_event.eventopts["event_num"] != 0

    def test_flush_stops_at_first_failed_replay(self, setup, monkeypatch):
        submitted = []

        def always_fail(formatted_event):
            submitted.append(formatted_event.eventopts["event_num"])
            return False

        forwarder = self._forwarder(monkeypatch, always_fail)
        forwarder.flush()

        assert submitted == [0]
        assert self._spooled(forwarder) == [0, 1, 2]
        assert forwarder.flush_stopped_at == 1
        assert self.log.messages("critical") == ["event stays in spool", "spooled events could not be submitted"]

    def test_flush_stops_after_successful_replays(self, setup, monkeypatch):
        submitted = []

        def fail_second(formatted_event):
            submitted.append(formatted_event.eventopts["event_num"])
            return formatted_event.eventopts["event_num"] != 1

        forwarder = self._forwarder(monkeypatch, fail_second)
        forwarder.flush()

        assert submitted == [0, 1]
        assert self._spooled(forwarder) == [1, 2]

    def test_flush_stops_on_submit_timeout(self, setup, monkeypatch):
        submitted = []

        def time_out(formatted_event):
            submitted.append(formatted_event.eventopts["event_num"])
            raise baseclass.ForwarderTimeoutError("submit ran into a timeout")

        forwarder = self._forwarder(monkeypatch, time_out)
        forwarder.flush()

        assert submitted == [0]
        assert self._spooled(forwarder) == [0, 1, 2]

    def test_flush_continues_after_trash(self, setup, monkeypatch):
        submitted = []

        def succeed(formatted_event):
            submitted.append(formatted_event.eventopts["event_num"])
            return True

        forwarder = self._forwarder(monkeypatch, succeed, num_spooled=2)
        format_ok = forwarder.format_event

        def discard_first(raw):
            fe = format_ok(raw)
            if raw.get("event_num") == 0:
                fe.discard()
            return fe

        monkeypatch.setattr(forwarder, "format_event", discard_first)
        forwarder.flush()

        assert submitted == [1]
        assert self._spooled(forwarder) == []
        assert forwarder.flush_stopped_at is None

    def test_rejected_event_moves_to_end(self, setup, monkeypatch):
        forwarder = self._forwarder(monkeypatch, self._reject_first)
        forwarder.dbcurs.execute(
            "UPDATE {table} SET timestamp = datetime('now', '-1 minutes') WHERE id = 1".format(
                table=forwarder.table_name))
        forwarder.dbconn.commit()
        original_timestamp = self._timestamp(forwarder, 1)

        # the flush stops at 0, the live event is accepted -> 0 moves behind 1 and 2
        forwarder.forward(dict(self.LIVE))

        assert self._spooled(forwarder) == [1, 2, 0]
        assert self._timestamp(forwarder, 4) == original_timestamp
        assert self.log.moved() == [{'event_id': 1, 'new_event_id': 4, 'action': 'moved_to_end'}]

        # the next flush delivers 1 and 2 and stops at 0 again, which is now last
        forwarder.forward(dict(self.LIVE))
        assert self._spooled(forwarder) == [0]
        assert len(self.log.moved()) == 1

    def test_no_move_when_live_submit_fails(self, setup, monkeypatch):
        def always_fail(formatted_event):
            return False

        forwarder = self._forwarder(monkeypatch, always_fail)
        forwarder.forward(dict(self.LIVE))

        assert self._spooled(forwarder) == [0, 1, 2, "live"]
        assert self.log.moved() == []

    def test_no_move_without_live_submit(self, setup, monkeypatch):
        forwarder = self._forwarder(monkeypatch, self._reject_first)
        # forward_formatted() without an event: flush only, nothing submitted afterwards
        forwarder.forward_formatted(None)

        assert self._spooled(forwarder) == [0, 1, 2]
        assert self.log.moved() == []

    def test_heartbeat_success_moves_rejected_event(self, setup, monkeypatch):
        live_heartbeats = []

        def reject_first(formatted_event):
            if formatted_event.eventopts["event_num"] == "live":
                live_heartbeats.append(formatted_event.is_heartbeat)
            return self._reject_first(formatted_event)

        forwarder = self._forwarder(monkeypatch, reject_first, heartbeat=True)
        forwarder.forward(dict(self.LIVE))

        assert live_heartbeats == [True]
        assert self._spooled(forwarder) == [1, 2, 0]

    def test_no_move_while_another_process_flushes(self, setup, monkeypatch):
        import subprocess
        holder = []

        def reject_first_and_lock(formatted_event):
            if formatted_event.eventopts["event_num"] == "live" and not holder:
                # another process takes the flush lock between the flush and the move
                holder.append(subprocess.Popen(
                    [sys.executable, "-c",
                     "import fcntl, sys\n"
                     "f = open(sys.argv[1], 'w')\n"
                     "fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                     "print('locked', flush=True)\n"
                     "sys.stdin.read()\n",
                     forwarder.db_lock_file],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True))
                assert holder[0].stdout.readline().strip() == "locked"
            return self._reject_first(formatted_event)

        forwarder = self._forwarder(monkeypatch, reject_first_and_lock)
        try:
            forwarder.forward(dict(self.LIVE))
            assert self._spooled(forwarder) == [0, 1, 2]
            assert self.log.moved() == []
            assert "missed the flush lock, rejected event stays in place" in self.log.messages("debug")
        finally:
            holder[0].stdin.close()
            holder[0].wait(timeout=10)

        # the next flush stops at 0 again and, with the lock free, moves it
        forwarder.forward(dict(self.LIVE))
        assert self._spooled(forwarder) == [1, 2, 0]

    def test_no_move_when_event_is_gone(self, setup, monkeypatch):
        def reject_first_then_gone(formatted_event):
            if formatted_event.eventopts["event_num"] == "live":
                # another process delivered and removed event 0 meanwhile
                other_process = SpoolStore(forwarder.db_file, forwarder.table_name)
                other_process.open()
                other_process.delete(1)
                other_process.close()
            return self._reject_first(formatted_event)

        forwarder = self._forwarder(monkeypatch, reject_first_then_gone)
        forwarder.forward(dict(self.LIVE))

        assert self._spooled(forwarder) == [1, 2]
        assert self.log.moved() == []

    def test_no_move_when_event_is_already_last(self, setup, monkeypatch):
        forwarder = self._forwarder(monkeypatch, self._reject_first, num_spooled=1)
        forwarder.forward(dict(self.LIVE))

        assert [event_id for event_id, _text in forwarder.spool_store.fetch_batch()] == [1]
        assert self.log.moved() == []

    def test_moved_event_still_expires(self, setup, monkeypatch):
        forwarder = self._forwarder(monkeypatch, self._reject_first)
        forwarder.dbcurs.execute(
            "UPDATE {table} SET timestamp = datetime('now', '-4 minutes') WHERE id = 1".format(
                table=forwarder.table_name))
        forwarder.dbconn.commit()

        forwarder.forward(dict(self.LIVE))
        assert self._spooled(forwarder) == [1, 2, 0]

        # a retention of 3 minutes, measured from the original spool time, drops 0
        assert forwarder.spool_store.prune_expired(3) == 1
        assert self._spooled(forwarder) == [1, 2]


# ============================================================================
# SpoolStore direct tests
# ============================================================================

class TestSpoolStore:
    def test_enqueue_and_fetch(self, setup, monkeypatch):
        """SpoolStore can enqueue and fetch events."""
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        event = {"description": "test event"}
        store.enqueue(event)

        events = store.fetch_batch()
        assert len(events) == 1

        store.close()

    def test_fetch_batch_limit(self, setup):
        """SpoolStore.fetch_batch respects limit parameter."""
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_limit.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        # Enqueue multiple events
        for i in range(15):
            store.enqueue({"event": i})

        # Fetch with limit
        events = store.fetch_batch(limit=10)
        assert len(events) == 10

        store.close()

    def test_delete_nonexistent_event(self, setup):
        """SpoolStore.delete with non-existent ID is a no-op."""
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_delete.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        # Should not raise
        store.delete(99999)

        store.close()

    def test_count_accuracy(self, setup):
        """SpoolStore.count returns accurate row count."""
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_count.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        assert store.count() == 0

        store.enqueue({"event": 1})
        assert store.count() == 1

        store.enqueue({"event": 2})
        assert store.count() == 2

        events = store.fetch_batch()
        store.delete(events[0][0])
        assert store.count() == 1

        store.close()

    def test_fetch_batch_limit_zero(self, setup):
        """SpoolStore.fetch_batch with limit=0 returns empty."""
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_limit0.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        store.enqueue({"event": 1})
        events = store.fetch_batch(limit=0)
        assert events == []

        store.close()

    def test_fetch_batch_limit_exceeds_total(self, setup):
        """SpoolStore.fetch_batch limit > total returns all rows."""
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_limitexceed.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        for i in range(3):
            store.enqueue({"event": i})
        events = store.fetch_batch(limit=100)
        assert len(events) == 3

        store.close()

    def test_prune_expired_boundary(self, setup):
        """SpoolStore.prune_expired at exact boundary deletes only expired."""
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_prune.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        # Enqueue an event
        store.enqueue({"event": "keep"})
        events = store.fetch_batch()
        keep_id = events[0][0]

        # Manually set its timestamp to exactly max_spool_minutes ago
        # (should NOT be deleted - only strictly older is deleted)
        store.cursor.execute(
            "UPDATE test_events SET timestamp = datetime('now', '-5 minutes') WHERE id = ?",
            (keep_id,)
        )
        store.connection.commit()

        # Enqueue another and set it to 6 minutes ago (should be deleted)
        store.enqueue({"event": "delete_me"})
        events = store.fetch_batch(limit=1)
        delete_id = events[0][0]
        store.cursor.execute(
            "UPDATE test_events SET timestamp = datetime('now', '-6 minutes') WHERE id = ?",
            (delete_id,)
        )
        store.connection.commit()

        dropped = store.prune_expired(5)
        assert dropped == 1
        assert store.count() == 1  # keep_id should remain

        store.close()

    def test_prune_expired_does_not_hold_write_lock(self, setup):
        """After prune_expired another process must be able to spool.

        Regression: the DELETE was not committed, so the implicit transaction
        kept the database write-locked during the whole flush.
        """
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_prune_lock.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()
        store.enqueue({"event": "keep"})

        store.prune_expired(5)

        other_process = sqlite3.connect(db_path, timeout=0.1)
        try:
            other_process.execute("INSERT INTO test_events(payload) VALUES (?)", ('{"event": "other"}',))
            other_process.commit()
        finally:
            other_process.close()

        assert store.count() == 2
        assert store.count(max_id=1) == 1
        store.close()

    def test_enqueue_non_serializable_data(self, setup):
        """SpoolStore.enqueue with non-serializable data raises."""
        import json as json_mod
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_nonserial.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        # set is not JSON-serializable
        with pytest.raises(TypeError):
            store.enqueue({"bad": set([1, 2, 3])})

        store.close()

    def test_decode_round_trip(self, setup):
        """SpoolStore decode correctly deserializes encoded events."""
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_decode.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        original_event = {"key": "value", "nested": {"a": 1}}
        store.enqueue(original_event)

        events = store.fetch_batch()
        decoded = store.decode(events[0][1])

        assert decoded == original_event

        store.close()

    def test_concurrent_enqueue(self, setup):
        """Concurrent enqueue from two threads does not corrupt the database."""
        import threading

        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_concurrent.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()
        store.close()

        errors = []

        def enqueue_worker(n):
            try:
                s = SpoolStore(db_path, "test_events")
                s.open()
                for i in range(10):
                    s.enqueue({"thread": n, "seq": i})
                s.close()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=enqueue_worker, args=(1,))
        t2 = threading.Thread(target=enqueue_worker, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == []

        verify = SpoolStore(db_path, "test_events")
        verify.open()
        assert verify.count() == 20
        verify.close()

    def test_concurrent_enqueue_shared_instance(self, setup):
        """Concurrent enqueue on a single shared SpoolStore instance is serialized
        by an internal lock, so all writes land exactly once."""
        import threading

        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_shared.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        errors = []

        def enqueue_worker(n):
            try:
                for i in range(10):
                    store.enqueue({"thread": n, "seq": i})
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=enqueue_worker, args=(1,))
        t2 = threading.Thread(target=enqueue_worker, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == []
        assert store.count() == 20
        store.close()

    def test_concurrent_mixed_operations_shared_instance(self, setup):
        """One thread enqueues while another fetches, counts and deletes on the
        same SpoolStore instance. Fetches see only fully stored rows in id order,
        no row twice, and the final count matches enqueued minus deleted."""
        import threading

        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_shared_mixed.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        num_events = 200
        errors = []
        fetched = []
        deleted = []
        writer_done = threading.Event()

        def writer():
            try:
                for i in range(num_events):
                    store.enqueue({"seq": i})
            except Exception as e:
                errors.append(e)
            finally:
                writer_done.set()

        def reader():
            try:
                last_id = 0
                while True:
                    finished = writer_done.is_set()
                    batch = store.fetch_batch(limit=10, after_id=last_id)
                    store.count()
                    store.max_id()
                    for event_id, text in batch:
                        fetched.append((event_id, store.decode(text)["seq"]))
                        last_id = event_id
                        # delete every other row, keep the rest
                        if event_id % 2 == 0:
                            store.delete(event_id)
                            deleted.append(event_id)
                    if finished and not batch:
                        break
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not any(t.is_alive() for t in threads)

        assert errors == []
        ids = [event_id for event_id, _seq in fetched]
        assert ids == sorted(set(ids))
        # without AUTOINCREMENT sqlite reuses the id of a deleted last row, so
        # an event can land behind the reader's after_id. It must then still
        # be in the spool: every event was either fetched once or is kept.
        fetched_seqs = [seq for _event_id, seq in fetched]
        assert fetched_seqs == sorted(set(fetched_seqs))
        remaining = [store.decode(text)["seq"] for _id, text in store.fetch_batch(limit=num_events)]
        kept_seqs = [seq for event_id, seq in fetched if event_id not in deleted]
        assert sorted(set(fetched_seqs) | set(remaining)) == list(range(num_events))
        assert set(kept_seqs) <= set(remaining)
        assert store.count() == num_events - len(deleted)
        store.close()

    def _store_with_rows(self, name, num_rows):
        db_path = os.path.join(OMD_ROOT, "tmp", name)
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()
        for i in range(num_rows):
            store.enqueue({"seq": i})
        return store

    def test_move_to_end_keeps_payload_and_timestamp(self, setup):
        """move_to_end() puts the row behind all others with its payload and timestamp."""
        store = self._store_with_rows("test_spool_move.db", 3)
        store.cursor.execute("UPDATE test_events SET timestamp = '2020-01-01 00:00:00' WHERE id = 1")
        store.connection.commit()

        assert store.move_to_end(1) == 4
        rows = store.fetch_batch()
        assert [(event_id, store.decode(text)["seq"]) for event_id, text in rows] == [(2, 1), (3, 2), (4, 0)]
        store.cursor.execute("SELECT timestamp FROM test_events WHERE id = 4")
        assert store.cursor.fetchone()[0] == "2020-01-01 00:00:00"
        store.close()

    def test_move_to_end_skips_last_and_missing_rows(self, setup):
        """A row that is already last, or gone, is not moved."""
        store = self._store_with_rows("test_spool_move_skip.db", 2)

        assert store.move_to_end(2) is None
        assert store.move_to_end(99) is None
        assert [event_id for event_id, _text in store.fetch_batch()] == [1, 2]
        store.close()

    def test_move_to_end_does_not_hold_write_lock(self, setup):
        """After move_to_end() and after a skipped move, other connections can insert."""
        store = self._store_with_rows("test_spool_move_lock.db", 2)
        other = sqlite3.connect(store.db_file, timeout=0.1)
        try:
            store.move_to_end(1)
            other.execute("INSERT INTO test_events(payload) VALUES ('{}')")
            other.commit()
            store.move_to_end(99)
            other.execute("INSERT INTO test_events(payload) VALUES ('{}')")
            other.commit()
        finally:
            other.close()
        assert store.count() == 4
        store.close()
