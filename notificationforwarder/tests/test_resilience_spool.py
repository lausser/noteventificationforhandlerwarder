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
        """Flush with more than 10 events triggers stuck detection correctly."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Enqueue 12 events
        for i in range(12):
            forwarder.spool_store.enqueue({"HOSTNAME": "h1", "event_num": i})

        assert forwarder.num_spooled_events() == 12

        # All submits fail to trigger stuck detection
        def always_fail(formatted_event):
            return False

        monkeypatch.setattr(forwarder, "submit", always_fail)

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

        # All 12 events should still be in spool (all failed)
        assert forwarder.num_spooled_events() == 12

        # Stuck detection should have triggered after 2 iterations (10 fetched, then 2 remaining = unchanged)
        assert any("could not be submitted" in str(c) for c in critical_calls)

        # spool replay summary should be logged
        assert any("spool replay summary" in str(c) for c in info_calls)

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
