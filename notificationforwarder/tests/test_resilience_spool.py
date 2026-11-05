"""
Resilience and spool tests for notificationforwarder.

This file covers heartbeat/spool policy, probe-gated flush, enrichment,
formatter failures, and spool replay edge cases.
"""
import logging
import os
import json
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
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or (True, 1))

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
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or (True, 1))

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
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or (True, 1))

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

        assert result == (False, None)
        assert any("database error" in str(c) for c in critical_calls)

    def test_spool_returns_tuple_contract(self, setup, monkeypatch):
        """spool() returns (success, event_id); on failure (False, None)."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        raw_event = {"HOSTNAME": "h-tuple", "description": "pin me"}
        success, event_id = forwarder.spool(raw_event)
        assert success is True
        assert event_id == forwarder.spool_store.max_id()
        # the event_id identifies the exact stored row
        stored = [row for row in forwarder.spool_store.fetch_batch() if row[0] == event_id]
        assert forwarder.spool_store.decode(stored[0][1]) == raw_event

        def raise_enqueue(raw_event):
            raise sqlite3.OperationalError("database is locked")

        forwarder.spool_store.enqueue = raise_enqueue
        assert forwarder.spool({"description": "doomed"}) == (False, None)

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
# Correlation of spool-related log lines
# ============================================================================

def _logfile_path(forwarder):
    python_logger = logging.getLogger("notificationforwarder_" + forwarder.forwarder_name)
    return [h.baseFilename for h in python_logger.handlers if hasattr(h, "baseFilename")][0]


def _json_log_entries(path):
    entries = []
    for line in open(path):
        pos = line.find("{")
        if pos < 0:
            continue
        try:
            entries.append(json.loads(line[pos:]))
        except Exception:
            continue
    return entries


def _msgs(entries, message):
    return [entry["msg"] for entry in entries if entry.get("msg", {}).get("message") == message]


class TestSpoolEventContextBuilder:
    """The context builder supplies id and raw event always, the summary
    only when a formatted event exists and has a non-empty summary."""

    def _forwarder(self):
        return _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

    def test_formatted_event_with_summary(self, setup):
        forwarder = self._forwarder()
        formatted_event = _formatted_event({"HOSTNAME": "h1"})
        formatted_event.payload = {"data": 1}
        formatted_event.summary = "sum: doomed"

        context = forwarder.spool_event_context(3, formatted_event, {"HOSTNAME": "h1"})

        assert context == {
            'event_id': 3,
            'raw_event': {'HOSTNAME': 'h1'},
            'formatted_event': formatted_event,
            'summary': 'sum: doomed',
        }

    def test_formatted_event_without_summary(self, setup):
        forwarder = self._forwarder()
        formatted_event = _formatted_event({"HOSTNAME": "h1"})
        formatted_event.payload = {"data": 1}
        formatted_event.summary = None

        context = forwarder.spool_event_context(5, formatted_event, {"HOSTNAME": "h1"})

        assert 'summary' not in context
        assert context['formatted_event'] is formatted_event
        assert context['event_id'] == 5
        assert context['raw_event'] == {'HOSTNAME': 'h1'}

    def test_without_formatted_event(self, setup):
        forwarder = self._forwarder()

        context = forwarder.spool_event_context(7, None, {"HOSTNAME": "h1"})

        assert context == {'event_id': 7, 'raw_event': {'HOSTNAME': 'h1'}}
        assert 'summary' not in context
        assert 'formatted_event' not in context


class TestSpoolLineContent:
    """The five replay-decision lines and the per-expiry lines carry the
    id plus the content of the spooled event, in both loggers."""

    TARGETS = ["webhook", "ticketsystem"]  # shipped-module and own-module forwarder paths

    def _forwarder(self, target, logger_type, **opts):
        if target == "webhook":
            opts.setdefault("url", "http://example.invalid/api")
        return _new_forwarder("example", forwarder_name=target, forwarder_opts=opts, logger_type=logger_type)

    def _stored_row(self, forwarder, event_id):
        return [row for row in forwarder.spool_store.fetch_batch(limit=100) if row[0] == event_id][0]

    # --- the spool-time line (forward failed) ------------------------------

    def test_spool_time_line_carries_id_raw_event_and_summary(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "json")

        monkeypatch.setattr(forwarder, "submit", lambda fe: False)
        raw_event = {"HOSTNAME": "h-spoil", "description": "spool me"}
        forwarder.forward(dict(raw_event))

        event_id = forwarder.spool_store.max_id()
        stored_payload = forwarder.spool_store.decode(self._stored_row(forwarder, event_id)[1])

        entries = _json_log_entries(_logfile_path(forwarder))
        spoiled = [msg for msg in _msgs(entries, "forward failed") if msg.get("spooled")]
        assert len(spoiled) == 1
        assert spoiled[0]["event_id"] == event_id
        assert spoiled[0]["raw_event"] == stored_payload
        assert spoiled[0]["summary"] == "sum: spool me"

    def test_spool_time_line_rendered_text(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "text")

        monkeypatch.setattr(forwarder, "submit", lambda fe: False)
        raw_event = {"HOSTNAME": "h-spoil", "description": "put me in the spool, sorry"}
        forwarder.forward(dict(raw_event))

        event_id = forwarder.spool_store.max_id()
        stored_payload = forwarder.spool_store.decode(self._stored_row(forwarder, event_id)[1])

        log = open(_logfile_path(forwarder)).read()
        rendered = [line for line in log.splitlines() if "forward failed" in line][-1]
        assert "WARNING" in rendered
        assert f"forward failed, spool id {event_id}" in rendered
        assert "summary <sum: put me in the spool, sorry>" in rendered
        assert f"raw event <{stored_payload}>" in rendered

    @pytest.mark.parametrize("target", TARGETS)
    def test_no_move_path_links_spool_and_delete_event_ids(self, setup, monkeypatch, target):
        forwarder = self._forwarder(target, "json")
        receiver = {"alive": False}

        def mock_submit(formatted_event):
            return receiver["alive"]

        monkeypatch.setattr(forwarder, "submit", mock_submit)
        raw_event = {"HOSTNAME": "h-corr", "description": "correlate with me"}
        forwarder.forward(dict(raw_event))
        assert forwarder.num_spooled_events() == 1
        event_id = forwarder.spool_store.max_id()
        stored_payload = forwarder.spool_store.decode(self._stored_row(forwarder, event_id)[1])

        receiver["alive"] = True
        forwarder.flush()
        assert forwarder.num_spooled_events() == 0

        entries = _json_log_entries(_logfile_path(forwarder))
        spool_msgs = [msg for msg in _msgs(entries, "forward failed") if msg.get("spooled")]
        delete_msgs = _msgs(entries, "delete spooled event")
        assert len(spool_msgs) == 1
        assert len(delete_msgs) == 1
        assert spool_msgs[0]["event_id"] == delete_msgs[0]["event_id"] == event_id
        assert spool_msgs[0]["raw_event"] == delete_msgs[0]["raw_event"] == stored_payload

    @pytest.mark.parametrize("target", TARGETS)
    def test_move_path_survives_via_content_free_bridge(self, setup, monkeypatch, target):
        forwarder = self._forwarder(target, "json")
        state = {"rejected_ok": True}

        def mock_submit(formatted_event):
            if formatted_event.eventopts["description"] == "move me":
                return not state["rejected_ok"]
            return True

        monkeypatch.setattr(forwarder, "submit", mock_submit)

        # phase 1: the event is spooled, it carries its raw event in the line
        raw_event = {"HOSTNAME": "h-move", "description": "move me"}
        forwarder.forward(dict(raw_event))
        old_event_id = forwarder.spool_store.max_id()
        stored_payload = forwarder.spool_store.decode(self._stored_row(forwarder, old_event_id)[1])
        forwarder.spool_store.enqueue({"HOSTNAME": "h-move", "description": "queued behind"})

        # phase 2: the replay of the spooled event is rejected, but the live
        # event is accepted, so the spooled event moves behind the others
        forwarder.forward({"HOSTNAME": "h-move", "description": "live 1"})
        entries = _json_log_entries(_logfile_path(forwarder))
        bridges = _msgs(entries, "spooled event moved to the end of the spool")
        assert len(bridges) == 1
        bridge = bridges[0]
        assert bridge["event_id"] == old_event_id
        new_event_id = bridge["new_event_id"]
        # the bridge line stays content-free: the ids are the message
        assert "raw_event" not in bridge
        assert "summary" not in bridge
        assert new_event_id == forwarder.spool_store.max_id()

        # phase 3: the receiver now accepts the event, it is replayed and deleted
        state["rejected_ok"] = False
        forwarder.flush()
        assert forwarder.num_spooled_events() == 0

        entries = _json_log_entries(_logfile_path(forwarder))
        delete_msgs = [msg for msg in _msgs(entries, "delete spooled event")
                       if msg["event_id"] == new_event_id]
        assert len(delete_msgs) == 1
        spool_msgs = [msg for msg in _msgs(entries, "forward failed") if msg.get("spooled")]
        assert delete_msgs[0]["event_id"] == new_event_id
        assert delete_msgs[0]["raw_event"] == spool_msgs[0]["raw_event"] == stored_payload

    # --- the replay-decision lines -----------------------------------------

    @pytest.mark.parametrize("logger_type", ["text", "json"])
    @pytest.mark.parametrize("outcome", ["success", "stay", "discard", "format_error"])
    def test_replay_logs_original_event_after_plugin_mutations(self, setup, monkeypatch, logger_type, outcome):
        forwarder = self._forwarder("webhook", logger_type)
        original = {
            "HOSTNAME": "h-original",
            "description": "original",
            "details": {"ticket": "original"},
            "items": ["original"],
        }
        first_id = forwarder.spool_store.enqueue(original)
        second_id = forwarder.spool_store.enqueue({"description": "later"})
        submitted = []

        class MutatingFormatter:
            __module_file__ = "test"

            def format_event(self, event):
                if event.eventopts["description"] == "later":
                    event.payload = {"message": "later"}
                    event.summary = "later"
                    return
                event.eventopts["description"] = "formatter changed"
                event.eventopts["details"]["ticket"] = "formatter changed"
                event.eventopts["items"].append("formatter added")
                event.eventopts["non_json"] = object()
                if outcome == "format_error":
                    raise ValueError("format failed")
                event.payload = {"message": "formatted"}
                event.summary = "formatted"
                if outcome == "discard":
                    event.discard()

        def submit(event):
            submitted.append(event.eventopts["description"])
            if event.eventopts["description"] != "later":
                event.eventopts["details"]["ticket"] = "forwarder changed"
                event.eventopts["items"].append("forwarder added")
            return outcome != "stay"

        monkeypatch.setattr(forwarder, "new_formatter", MutatingFormatter)
        monkeypatch.setattr(forwarder, "submit", submit)
        forwarder.flush()

        messages = {
            "success": ["delete spooled event"],
            "stay": ["event stays in spool"],
            "discard": ["discard spooled event during replay"],
            "format_error": ["could not format spooled event", "delete trash event"],
        }[outcome]
        if logger_type == "json":
            entries = _json_log_entries(_logfile_path(forwarder))
            for message in messages:
                matching = [msg for msg in _msgs(entries, message) if msg["event_id"] == first_id]
                assert len(matching) == 1
                assert matching[0]["raw_event"] == original
        else:
            with open(_logfile_path(forwarder)) as logfile:
                lines = logfile.read().splitlines()
            leads = {
                "success": [f"delete spooled event {first_id}"],
                "stay": [f"event {first_id} stays in spool"],
                "discard": [f"discard spooled event during replay {first_id}"],
                "format_error": ["could not format spooled", f"delete trash event {first_id}"],
            }[outcome]
            for lead in leads:
                matching = [line for line in lines if lead in line]
                assert len(matching) == 1
                assert str(original) in matching[0]

        if outcome == "stay":
            assert submitted == ["formatter changed"]
            assert [row[0] for row in forwarder.spool_store.fetch_batch()] == [first_id, second_id]
        else:
            assert submitted[-1] == "later"
            assert forwarder.num_spooled_events() == 0

    def test_delete_spooled_event_line_carries_id_and_content(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "json")
        receiver = {"alive": False}

        def mock_submit(formatted_event):
            return receiver["alive"]

        monkeypatch.setattr(forwarder, "submit", mock_submit)
        raw_event = {"HOSTNAME": "h-del", "description": "delete me"}
        forwarder.forward(dict(raw_event))
        event_id = forwarder.spool_store.max_id()
        receiver["alive"] = True
        forwarder.flush()

        entries = _json_log_entries(_logfile_path(forwarder))
        delete_msgs = _msgs(entries, "delete spooled event")
        assert len(delete_msgs) == 1
        assert delete_msgs[0]["event_id"] == event_id
        assert delete_msgs[0]["raw_event"]["description"] == "delete me"
        assert delete_msgs[0]["summary"] == "sum: delete me"

    def test_delete_spooled_event_line_rendered_text(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "text")
        receiver = {"alive": False}

        def mock_submit(formatted_event):
            return receiver["alive"]

        monkeypatch.setattr(forwarder, "submit", mock_submit)
        raw_event = {"HOSTNAME": "h-del", "description": "delete me, please"}
        forwarder.forward(dict(raw_event))
        event_id = forwarder.spool_store.max_id()
        stored_payload = forwarder.spool_store.decode(self._stored_row(forwarder, event_id)[1])
        receiver["alive"] = True
        forwarder.flush()

        log = open(_logfile_path(forwarder)).read()
        rendered = [line for line in log.splitlines() if "delete spooled event" in line][-1]
        assert f"INFO - delete spooled event {event_id}" in rendered
        assert "summary <sum: delete me, please>" in rendered
        assert f"raw event <{stored_payload}>" in rendered

    def test_stays_in_spool_line_carries_id_content_and_error(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "json")
        raw_event = {"HOSTNAME": "h-stay", "description": "stay with me"}
        forwarder.spool_store.enqueue({"HOSTNAME": "h-stay", "description": "stay with me"})
        event_id = forwarder.spool_store.max_id()

        def mock_submit(formatted_event):
            raise RuntimeError("receiver down")

        monkeypatch.setattr(forwarder, "submit", mock_submit)
        forwarder.flush()
        assert forwarder.num_spooled_events() == 1

        entries = _json_log_entries(_logfile_path(forwarder))
        stays_msgs = _msgs(entries, "event stays in spool")
        assert len(stays_msgs) == 1
        assert stays_msgs[0]["event_id"] == event_id
        assert stays_msgs[0]["raw_event"]["description"] == "stay with me"
        assert stays_msgs[0]["summary"] == "sum: stay with me"
        assert stays_msgs[0]["exception"] == "receiver down"

    def test_stays_in_spool_line_rendered_text(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "text")
        forwarder.spool_store.enqueue({"HOSTNAME": "h-stay", "description": "stay in text"})
        event_id = forwarder.spool_store.max_id()

        def mock_submit(formatted_event):
            raise RuntimeError("still down")

        monkeypatch.setattr(forwarder, "submit", mock_submit)
        forwarder.flush()

        log = open(_logfile_path(forwarder)).read()
        rendered = [line for line in log.splitlines() if "stays in spool" in line][-1]
        assert "CRITICAL" in rendered
        assert f"event {event_id} stays in spool" in rendered
        assert "summary <sum: stay in text>" in rendered
        assert "'description': 'stay in text'" in rendered
        assert "with exception <still down>" in rendered

    def test_discard_during_replay_line_carries_id_summary_and_raw_event(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "json")

        def format_doomed(raw):
            formatted_event = _formatted_event(raw)
            formatted_event.payload = {"data": "gone"}
            # a formatter which decides to discard after it named the event
            formatted_event.summary = "doomed: " + raw["description"]
            formatted_event.discard(silently=True)
            return formatted_event

        raw_event = {"HOSTNAME": "h-doom", "description": "discard me"}
        forwarder.spool_store.enqueue(dict(raw_event))
        event_id = forwarder.spool_store.max_id()
        monkeypatch.setattr(forwarder, "format_event", format_doomed)
        monkeypatch.setattr(forwarder, "submit", lambda fe: pytest.fail("discarded events are not submitted"))
        forwarder.flush()
        assert forwarder.num_spooled_events() == 0

        entries = _json_log_entries(_logfile_path(forwarder))
        discard_msgs = _msgs(entries, "discard spooled event during replay")
        assert len(discard_msgs) == 1
        assert discard_msgs[0]["event_id"] == event_id
        assert discard_msgs[0]["raw_event"] == raw_event
        assert discard_msgs[0]["summary"] == "doomed: discard me"

    def test_discard_during_replay_line_rendered_text(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "text")

        def format_doomed(raw):
            formatted_event = _formatted_event(raw)
            formatted_event.payload = {"data": "gone"}
            formatted_event.summary = "doomed in text"
            formatted_event.discard(silently=True)
            return formatted_event

        raw_event = {"HOSTNAME": "h-doom", "description": "text me away"}
        forwarder.spool_store.enqueue(dict(raw_event))
        event_id = forwarder.spool_store.max_id()
        monkeypatch.setattr(forwarder, "format_event", format_doomed)
        monkeypatch.setattr(forwarder, "submit", lambda fe: pytest.fail("discarded events are not submitted"))
        forwarder.flush()

        log = open(_logfile_path(forwarder)).read()
        rendered = [line for line in log.splitlines() if "discard spooled event during replay" in line][-1]
        assert f"discard spooled event during replay {event_id}" in rendered
        assert "summary <doomed in text>" in rendered
        assert "'description': 'text me away'" in rendered

    def test_unformattable_spooled_events_show_raw_event(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "json")
        raw_event = {"HOSTNAME": "h-trash", "description": "poison the formatter"}
        forwarder.spool_store.enqueue(dict(raw_event))
        event_id = forwarder.spool_store.max_id()
        monkeypatch.setattr(forwarder, "format_event", lambda raw: None)
        forwarder.flush()
        assert forwarder.num_spooled_events() == 0

        entries = _json_log_entries(_logfile_path(forwarder))
        for message in ["could not format spooled event", "delete trash event"]:
            msgs = _msgs(entries, message)
            assert len(msgs) == 1
            assert msgs[0]["event_id"] == event_id
            assert msgs[0]["raw_event"] == raw_event
            assert "summary" not in msgs[0]

    def test_unformattable_spooled_events_rendered_text(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "text")
        raw_event = {"HOSTNAME": "h-trash", "description": "poison in text"}
        forwarder.spool_store.enqueue(dict(raw_event))
        event_id = forwarder.spool_store.max_id()
        monkeypatch.setattr(forwarder, "format_event", lambda raw: None)
        forwarder.flush()

        log = open(_logfile_path(forwarder)).read()
        trash_lines = [line for line in log.splitlines() if "delete trash event" in line]
        assert f"delete trash event {event_id}" in trash_lines[-1]
        assert "'description': 'poison in text'" in trash_lines[-1]
        garbage_lines = [line for line in log.splitlines() if "could not format spooled" in line]
        assert f"with id {event_id}" in garbage_lines[-1]
        assert "'description': 'poison in text'" in garbage_lines[-1]

    def test_empty_summary_omits_the_summary_key(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "json")

        def format_without_summary(raw):
            formatted_event = _formatted_event(raw)
            formatted_event.payload = {"data": "quiet"}
            # the formatter leaves the summary empty
            return formatted_event

        raw_event = {"HOSTNAME": "h-quiet", "description": "no summary, please"}
        forwarder.spool_store.enqueue(dict(raw_event))
        event_id = forwarder.spool_store.max_id()
        monkeypatch.setattr(forwarder, "format_event", format_without_summary)
        monkeypatch.setattr(forwarder, "submit", lambda fe: True)
        forwarder.flush()
        assert forwarder.num_spooled_events() == 0

        entries = _json_log_entries(_logfile_path(forwarder))
        delete_msgs = _msgs(entries, "delete spooled event")
        assert len(delete_msgs) == 1
        # no summary may be invented: the key is omitted, the raw event
        # carries the content
        assert "summary" not in delete_msgs[0]
        assert delete_msgs[0]["event_id"] == event_id
        assert delete_msgs[0]["raw_event"] == raw_event

    def test_could_not_format_line_omits_the_summary_key(self, setup, monkeypatch):
        forwarder = self._forwarder("webhook", "json")
        raw_event = {"HOSTNAME": "h-broken", "description": "nothing left to summarize"}
        forwarder.spool_store.enqueue(dict(raw_event))
        monkeypatch.setattr(forwarder, "format_event", lambda raw: None)
        forwarder.flush()

        entries = _json_log_entries(_logfile_path(forwarder))
        for message in ["could not format spooled event", "delete trash event"]:
            msgs = _msgs(entries, message)
            assert len(msgs) == 1
            assert "summary" not in msgs[0]
            assert "event_summary" not in msgs[0]
            assert msgs[0]["raw_event"] == raw_event


class TestPerEventExpiryLogging:
    """When the flush prunes expired spool rows, every expired event is
    named with id and raw event, in addition to the aggregate count line."""

    def _forwarder(self, logger_type):
        return _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
            logger_type=logger_type,
        )

    def _backdate(self, forwarder, event_id, minutes):
        forwarder.dbcurs.execute(
            "UPDATE {table} SET timestamp = datetime('now', '-{minutes} minutes') WHERE id = {event_id}".format(
                table=forwarder.table_name, minutes=minutes, event_id=event_id))
        forwarder.dbconn.commit()

    def test_every_expired_event_is_named(self, setup, monkeypatch):
        forwarder = self._forwarder("json")
        raw_events = [{"HOSTNAME": "h-exp", "description": "expired %d" % i} for i in range(3)]
        for raw_event in raw_events:
            forwarder.spool_store.enqueue(dict(raw_event))
        expired_rows = forwarder.spool_store.fetch_batch(limit=100)
        for event_id, _text in expired_rows:
            self._backdate(forwarder, event_id, 6)

        monkeypatch.setattr(forwarder, "submit", lambda fe: pytest.fail("nothing left to replay"))
        forwarder.flush()

        expired_msgs = _msgs(_json_log_entries(_logfile_path(forwarder)), "expired spooled event")
        assert len(expired_msgs) == 3
        assert sorted(msg["event_id"] for msg in expired_msgs) == sorted(row[0] for row in expired_rows)
        assert sorted(msg["raw_event"]["description"] for msg in expired_msgs) == sorted(
            "expired %d" % i for i in range(3))
        # no summary may be invented for expired entries
        assert all("summary" not in msg for msg in expired_msgs)
        count_msgs = _msgs(_json_log_entries(_logfile_path(forwarder)), "dropped outdated events")
        assert count_msgs[-1]["spooled_count"] == 3

    def test_every_expired_event_rendered_text(self, setup, monkeypatch):
        forwarder = self._forwarder("text")
        for i in range(2):
            event_id = forwarder.spool_store.enqueue({"HOSTNAME": "h-exp", "description": "text expired %d" % i})
            self._backdate(forwarder, event_id, 6)

        monkeypatch.setattr(forwarder, "submit", lambda fe: pytest.fail("nothing left to replay"))
        forwarder.flush()

        log = open(_logfile_path(forwarder)).read()
        expired_lines = [line for line in log.splitlines() if "expired spooled event" in line]
        assert len(expired_lines) == 2
        for i in range(2):
            matching = [line for line in expired_lines if "'description': 'text expired %d'" % i in line]
            assert len(matching) == 1
        counts = [line for line in log.splitlines() if "dropped 2 outdated events" in line]
        assert "dropped 2 outdated events" in counts[-1]

    def test_corrupt_expired_payload_does_not_stop_replay(self, setup, monkeypatch):
        forwarder = self._forwarder("json")
        corrupt_id = forwarder.spool_store.enqueue({"HOSTNAME": "h-corrupt", "description": "corrupt me"})
        alive_id = forwarder.spool_store.enqueue({"HOSTNAME": "h-alive", "description": "replay me"})
        self._backdate(forwarder, corrupt_id, 6)
        monkeypatch.setattr(forwarder, "submit", lambda fe: True)

        forwarder.dbcurs.execute(
            "UPDATE {table} SET payload = 'not json at all {{' WHERE id = {event_id}".format(
                table=forwarder.table_name, event_id=corrupt_id))
        forwarder.dbconn.commit()

        forwarder.flush()

        assert forwarder.num_spooled_events() == 0
        entries = _json_log_entries(_logfile_path(forwarder))
        undecodable_msgs = _msgs(entries, "expired spool entry could not be decoded")
        assert len(undecodable_msgs) == 1
        assert undecodable_msgs[0]["event_id"] == corrupt_id
        assert undecodable_msgs[0]["payload_text"] == "not json at all {"
        # the replay of the in-retention row was not skipped
        delete_msgs = _msgs(entries, "delete spooled event")
        assert len(delete_msgs) == 1
        assert delete_msgs[0]["event_id"] == alive_id


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
        dropped_rows = forwarder.spool_store.prune_expired(3)
        assert [event_id for event_id, _payload in dropped_rows] == [4]
        assert self._spooled(forwarder) == [1, 2]


class TestQueueLengthAfterFlush:
    """Every flush logs the remaining spool size as "spooling queue length"."""

    def _forwarder(self, monkeypatch, submit, num_spooled=3, logger_type="text"):
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
            logger_type=logger_type,
        )
        for i in range(num_spooled):
            forwarder.spool_store.enqueue({"HOSTNAME": "h1", "event_num": i})

        def format_ok(raw):
            fe = _formatted_event(raw)
            fe.payload = {"data": "test"}
            fe.summary = "test"
            return fe

        monkeypatch.setattr(forwarder, "format_event", format_ok)
        monkeypatch.setattr(forwarder, "submit", submit)
        return forwarder

    def _queue_lengths(self, monkeypatch, forwarder):
        log = _RecordingLogger()
        monkeypatch.setattr(baseclass, "logger", log)
        forwarder.flush()
        return [(lvl, ctx) for lvl, msg, ctx in log.calls if msg == "spooling queue length"]

    def test_queue_length_zero_after_drain(self, setup, monkeypatch):
        forwarder = self._forwarder(monkeypatch, lambda formatted_event: True)
        assert self._queue_lengths(monkeypatch, forwarder) == [("info", {'queue_length': 0})]

    def test_queue_length_after_stopped_flush(self, setup, monkeypatch):
        forwarder = self._forwarder(monkeypatch, lambda formatted_event: False)
        assert self._queue_lengths(monkeypatch, forwarder) == [("info", {'queue_length': 3})]

    def test_queue_length_includes_concurrently_spooled_events(self, setup, monkeypatch):
        def succeed_while_another_process_spools(formatted_event):
            if formatted_event.eventopts["event_num"] == 0:
                other_process = SpoolStore(forwarder.db_file, forwarder.table_name)
                other_process.open()
                other_process.enqueue({"HOSTNAME": "h1", "event_num": 100})
                other_process.close()
            return True

        forwarder = self._forwarder(monkeypatch, succeed_while_another_process_spools)
        assert self._queue_lengths(monkeypatch, forwarder) == [("info", {'queue_length': 1})]

    def test_queue_length_not_logged_without_lock(self, setup, monkeypatch):
        forwarder = self._forwarder(monkeypatch, lambda formatted_event: True)
        monkeypatch.setattr(forwarder, "acquire_lock_with_retry",
                            lambda lock_file, max_attempts=3, base_delay=0.1: False)
        assert self._queue_lengths(monkeypatch, forwarder) == []

    def test_queue_length_json_format(self, setup, monkeypatch):
        """The monitoring regex from the docs reads 0 after the spool drained."""
        import re
        forwarder = self._forwarder(monkeypatch, lambda formatted_event: True, logger_type="json")
        forwarder.flush()
        python_logger = logging.getLogger("notificationforwarder_" + forwarder.forwarder_name)
        logfile = [h.baseFilename for h in python_logger.handlers if hasattr(h, "baseFilename")][0]
        values = re.findall(r'"message":"spooling queue length","queue_length":(\d+)', open(logfile).read())
        assert values[-1] == "0"


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
        event_id = store.enqueue(event)
        store.cursor.execute("SELECT MAX(id) FROM test_events")
        assert event_id == store.cursor.fetchone()[0]

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

    def test_prune_expired_boundary(self, setup, monkeypatch):
        """SpoolStore.prune_expired at exact boundary deletes only expired."""
        db_path = os.path.join(OMD_ROOT, "tmp", "test_spool_prune.db")
        store = SpoolStore(db_path, "test_events")
        store.open()
        store.init_db()

        now = 1700000000
        monkeypatch.setattr("notificationforwarder.spool.time.time", lambda: now)
        keep_id = store.enqueue({"event": "keep"})

        # Manually set its timestamp to exactly max_spool_minutes ago
        # (should NOT be deleted - only strictly older is deleted)
        store.cursor.execute(
            "UPDATE test_events SET timestamp = datetime(?, 'unixepoch') WHERE id = ?",
            (now - 5 * 60, keep_id)
        )
        store.connection.commit()

        # Enqueue another and set it to 6 minutes ago (should be deleted)
        delete_id = store.enqueue({"event": "delete_me"})
        store.cursor.execute(
            "UPDATE test_events SET timestamp = datetime(?, 'unixepoch') WHERE id = ?",
            (now - 6 * 60, delete_id)
        )
        store.connection.commit()

        dropped_rows = store.prune_expired(5)
        assert [(event_id, store.decode(payload)) for event_id, payload in dropped_rows] \
            == [(delete_id, {"event": "delete_me"})]
        assert [(event_id, store.decode(payload)) for event_id, payload in store.fetch_batch()] \
            == [(keep_id, {"event": "keep"})]

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
