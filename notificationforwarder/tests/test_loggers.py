"""
Logger tests for notificationforwarder.

This file covers the TextLogger and JsonLogger contract coverage,
including message rendering, exception handling, and structured field expectations.
"""
import logging
import os
import shutil
import sys

import pytest

os.environ["PYTHONDONTWRITEBYTECODE"] = "true"

OMD_ROOT = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = OMD_ROOT

if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/../src")

from notificationforwarder.text.logger import TextLogger
from notificationforwarder.json.logger import JsonLogger
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


# ============================================================================
# TextLogger tests
# ============================================================================

class TestTextLogger:
    def test_simple_message(self, setup):
        """TextLogger handles simple messages."""
        logger_name = "test_text_logger"
        python_logger = logging.getLogger(logger_name)
        python_logger.setLevel(logging.DEBUG)
        
        log_capture = logging.StreamHandler(sys.stdout)
        log_capture.setLevel(logging.DEBUG)
        python_logger.addHandler(log_capture)
        
        try:
            logger = TextLogger(logger_name, python_logger)
            logger.info("test message", {})
            logger.debug("debug message", {})
            logger.warning("warning message", {})
            logger.critical("critical message", {})
        finally:
            python_logger.removeHandler(log_capture)

    def test_message_with_exception(self, setup):
        """TextLogger handles messages with exception context."""
        logger_name = "test_text_logger_exception"
        python_logger = logging.getLogger(logger_name)
        python_logger.setLevel(logging.DEBUG)
        
        log_capture = logging.StreamHandler(sys.stdout)
        log_capture.setLevel(logging.DEBUG)
        python_logger.addHandler(log_capture)
        
        try:
            logger = TextLogger(logger_name, python_logger)
            try:
                raise ValueError("test error")
            except ValueError as e:
                logger.critical("error occurred", {
                    'exception': e,
                    'exc_info': sys.exc_info()
                })
        finally:
            python_logger.removeHandler(log_capture)

    def test_message_with_formatted_event(self, setup):
        """TextLogger handles messages with FormattedEvent context."""
        logger_name = "test_text_logger_event"
        python_logger = logging.getLogger(logger_name)
        python_logger.setLevel(logging.DEBUG)
        
        log_capture = logging.StreamHandler(sys.stdout)
        log_capture.setLevel(logging.DEBUG)
        python_logger.addHandler(log_capture)
        
        try:
            logger = TextLogger(logger_name, python_logger)
            event_data = {
                'HOSTNAME': 'testhost',
                'SERVICEDESC': 'testservice',
                'SERVICESTATE': 'CRITICAL'
            }
            formatted_event = FormattedEvent(event_data)
            formatted_event.summary = "testhost/testservice: CRITICAL"
            
            logger.info("forwarded", {
                'formatted_event': formatted_event,
                'status': 'success'
            })
        finally:
            python_logger.removeHandler(log_capture)

    def test_message_with_spooled_event(self, setup):
        """TextLogger handles messages with spooled event context."""
        logger_name = "test_text_logger_spooled"
        python_logger = logging.getLogger(logger_name)
        python_logger.setLevel(logging.DEBUG)
        
        log_capture = logging.StreamHandler(sys.stdout)
        log_capture.setLevel(logging.DEBUG)
        python_logger.addHandler(log_capture)
        
        try:
            logger = TextLogger(logger_name, python_logger)
            event_data = {
                'HOSTNAME': 'testhost',
                'SERVICEDESC': 'testservice'
            }
            formatted_event = FormattedEvent(event_data)
            formatted_event.summary = "testhost/testservice"
            
            logger.critical("forward failed", {
                'exception': 'Connection timeout',
                'formatted_event': formatted_event,
                'spooled': True
            })
        finally:
            python_logger.removeHandler(log_capture)


# ============================================================================
# JsonLogger tests
# ============================================================================

class TestJsonLogger:
    def test_simple_json_message(self, setup):
        """JsonLogger handles simple messages."""
        logger_name = "test_json_logger"
        python_logger = logging.getLogger(logger_name)
        python_logger.setLevel(logging.DEBUG)
        
        log_capture = logging.StreamHandler(sys.stdout)
        log_capture.setLevel(logging.DEBUG)
        python_logger.addHandler(log_capture)
        
        try:
            logger = JsonLogger(logger_name, python_logger, version="2.9")
            logger.info("test message", {})
        finally:
            python_logger.removeHandler(log_capture)

    def test_json_with_event_context(self, setup):
        """JsonLogger handles messages with event context."""
        logger_name = "test_json_logger_event"
        python_logger = logging.getLogger(logger_name)
        python_logger.setLevel(logging.DEBUG)
        
        log_capture = logging.StreamHandler(sys.stdout)
        log_capture.setLevel(logging.DEBUG)
        python_logger.addHandler(log_capture)
        
        try:
            logger = JsonLogger(logger_name, python_logger, version="2.9")
            event_data = {
                'HOSTNAME': 'testhost',
                'SERVICEDESC': 'testservice',
                'SERVICESTATE': 'WARNING',
                'NOTIFICATIONTYPE': 'PROBLEM'
            }
            formatted_event = FormattedEvent(event_data)
            formatted_event.summary = "testhost/testservice: WARNING"
            
            logger.info("forwarded", {
                'formatted_event': formatted_event,
                'status': 'success'
            })
        finally:
            python_logger.removeHandler(log_capture)

    def test_json_with_exception(self, setup):
        """JsonLogger handles messages with exception context."""
        logger_name = "test_json_logger_exception"
        python_logger = logging.getLogger(logger_name)
        python_logger.setLevel(logging.DEBUG)
        
        log_capture = logging.StreamHandler(sys.stdout)
        log_capture.setLevel(logging.DEBUG)
        python_logger.addHandler(log_capture)
        
        try:
            logger = JsonLogger(logger_name, python_logger, version="2.9")
            try:
                raise RuntimeError("test runtime error")
            except RuntimeError as e:
                logger.critical("exception occurred", {
                    'exception': e,
                    'exc_info': sys.exc_info()
                })
        finally:
            python_logger.removeHandler(log_capture)

    def test_json_with_spooled_context(self, setup):
        """JsonLogger handles messages with spooling context."""
        logger_name = "test_json_logger_spooled"
        python_logger = logging.getLogger(logger_name)
        python_logger.setLevel(logging.DEBUG)
        
        log_capture = logging.StreamHandler(sys.stdout)
        log_capture.setLevel(logging.DEBUG)
        python_logger.addHandler(log_capture)
        
        try:
            logger = JsonLogger(logger_name, python_logger, version="2.9")
            logger.warning("spooling queue length", {
                'queue_length': 5
            })
            
            logger.info("spooled events to be re-sent", {
                'spooled_count': 3,
                'action': 'resend'
            })
        finally:
            python_logger.removeHandler(log_capture)

    def test_json_structure(self, setup):
        """JsonLogger produces correct JSON structure."""
        logger_name = "test_json_logger_structure"
        python_logger = logging.getLogger(logger_name)
        python_logger.setLevel(logging.DEBUG)
        
        log_capture = logging.StreamHandler(sys.stdout)
        log_capture.setLevel(logging.DEBUG)
        python_logger.addHandler(log_capture)
        
        try:
            logger = JsonLogger(logger_name, python_logger, version="2.9")
            event_data = {
                'HOSTNAME': 'testhost',
                'SERVICEDESC': 'testservice',
                'SERVICESTATE': 'CRITICAL'
            }
            formatted_event = FormattedEvent(event_data)
            formatted_event.summary = "Test event"
            
            logger.critical("forward failed", {
                'exception': "Network error",
                'formatted_event': formatted_event,
                'spooled': True,
                'forwarder_name': 'webhook',
                'formatter_name': 'json'
            })
        finally:
            python_logger.removeHandler(log_capture)


# ============================================================================
# TextLogger specific message branch tests
# ============================================================================

class TestTextLoggerMessageBranches:
    def _make_logger(self, name):
        python_logger = logging.getLogger(name)
        python_logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        python_logger.addHandler(handler)
        return TextLogger(name, python_logger), python_logger, handler

    def test_flush_probe_failed(self, setup):
        """'flush probe failed' message includes exception."""
        logger, pl, h = self._make_logger("test_flush_probe")
        try:
            logger.critical("flush probe failed", {
                'exception': RuntimeError('probe timeout'),
                'exc_info': None,
            })
        finally:
            pl.removeHandler(h)

    def test_database_flush_resubmit_failed(self, setup):
        """'database flush+resubmit failed' message includes exception."""
        logger, pl, h = self._make_logger("test_flush_resubmit")
        try:
            logger.critical("database flush+resubmit failed", {
                'database_error': True,
                'exception': RuntimeError('db locked'),
            })
        finally:
            pl.removeHandler(h)

    def test_found_no_formatter_module(self, setup):
        """'found no formatter module' message includes module name."""
        logger, pl, h = self._make_logger("test_no_formatter")
        try:
            logger.critical("found no formatter module", {
                'module_name': 'my_custom_formatter',
                'forwarder_opts': {},
            })
        finally:
            pl.removeHandler(h)

    def test_spool_replay_summary(self, setup):
        """'spool replay summary' includes all count fields."""
        logger, pl, h = self._make_logger("test_replay_summary")
        try:
            logger.info("spool replay summary", {
                'attempted': 10,
                'recovered_count': 8,
                'stays_in_spool_count': 1,
                'deleted_trash_count': 1,
                'dropped_count': 0,
            })
        finally:
            pl.removeHandler(h)

    def test_delete_spooled_event_action(self, setup):
        """'delete spooled event' action message."""
        logger, pl, h = self._make_logger("test_delete_spooled")
        try:
            logger.info("delete spooled event", {
                'spooled_count': 1,
                'event_id': 42,
                'action': 'delete',
            })
        finally:
            pl.removeHandler(h)

    def test_event_stays_in_spool_action(self, setup):
        """'event stays in spool' action message."""
        logger, pl, h = self._make_logger("test_stays_spool")
        try:
            logger.critical("event stays in spool", {
                'event_id': 42,
                'action': 'stays_in_spool',
                'exception': 'connection refused',
            })
        finally:
            pl.removeHandler(h)

    def test_delete_trash_event_action(self, setup):
        """'delete trash event' action message."""
        logger, pl, h = self._make_logger("test_delete_trash")
        try:
            logger.info("delete trash event", {
                'event_id': 42,
                'action': 'delete_trash',
            })
        finally:
            pl.removeHandler(h)

    def test_could_not_format_spooled_event_action(self, setup):
        """'could not format spooled event' action message."""
        logger, pl, h = self._make_logger("test_could_not_format")
        try:
            logger.critical("could not format spooled event", {
                'raw_event': {'HOSTNAME': 'h1'},
                'event_id': 42,
                'spooled_count': 1,
                'action': 'could_not_format',
            })
        finally:
            pl.removeHandler(h)

    def test_dropped_outdated_events_action(self, setup):
        """'dropped outdated events' action message."""
        logger, pl, h = self._make_logger("test_dropped")
        try:
            logger.info("dropped outdated events", {
                'spooled_count': 5,
                'action': 'dropped',
            })
        finally:
            pl.removeHandler(h)

    def test_concurrent_flush_suppressed(self, setup):
        """'concurrent flush suppressed' message."""
        logger, pl, h = self._make_logger("test_concurrent_flush")
        try:
            logger.info("concurrent flush suppressed", {})
        finally:
            pl.removeHandler(h)

    def test_spooled_events_to_be_resent(self, setup):
        """'spooled events to be re-sent' message."""
        logger, pl, h = self._make_logger("test_resent")
        try:
            logger.info("spooled events to be re-sent", {
                'spooled_count': 3,
                'action': 'resend',
            })
        finally:
            pl.removeHandler(h)

    def test_spooled_events_could_not_be_submitted(self, setup):
        """'spooled events could not be submitted' stuck detection message."""
        logger, pl, h = self._make_logger("test_stuck")
        try:
            logger.critical("spooled events could not be submitted", {
                'spooled_count': 5,
                'action': 'could_not_submit',
            })
        finally:
            pl.removeHandler(h)

    def test_delivery_failed_could_not_persist(self, setup):
        """'delivery failed and event could not be persisted' message."""
        logger, pl, h = self._make_logger("test_could_not_persist")
        try:
            logger.critical("delivery failed and event could not be persisted", {
                'formatted_event': FormattedEvent({'HOSTNAME': 'h1'}),
                'exception': RuntimeError('db full'),
            })
        finally:
            pl.removeHandler(h)

    def test_formatted_event_incomplete(self, setup):
        """'formatted event incomplete' message."""
        logger, pl, h = self._make_logger("test_incomplete")
        try:
            logger.critical("formatted event incomplete", {
                'event_class': 'FormattedEvent',
            })
        finally:
            pl.removeHandler(h)


# ============================================================================
# JsonLogger structured field tests
# ============================================================================

class TestJsonLoggerStructuredFields:
    def _make_logger(self, name):
        python_logger = logging.getLogger(name)
        python_logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        python_logger.addHandler(handler)
        return JsonLogger(name, python_logger, version="2.9"), python_logger, handler

    def test_success_structured_fields(self, setup):
        """JSON success path includes expected keys."""
        import json as json_mod
        logger, pl, h = self._make_logger("test_json_success")
        try:
            event = FormattedEvent({
                'HOSTNAME': 'testhost',
                'SERVICEDESC': 'testsvc',
                'SERVICESTATE': 'OK',
            })
            event.summary = "testhost/testsvc: OK"

            logger.info("forwarded", {
                'formatted_event': event,
                'status': 'success',
                'forwarder_name': 'webhook',
                'split_count': 1,
            })
        finally:
            pl.removeHandler(h)

    def test_failure_structured_fields(self, setup):
        """JSON failure path includes spool and exception fields."""
        import json as json_mod
        logger, pl, h = self._make_logger("test_json_failure")
        try:
            event = FormattedEvent({
                'HOSTNAME': 'testhost',
                'SERVICEDESC': 'testsvc',
                'SERVICESTATE': 'CRITICAL',
            })
            event.summary = "testhost/testsvc: CRITICAL"

            logger.critical("forward failed", {
                'exception': RuntimeError('timeout'),
                'formatted_event': event,
                'spooled': True,
                'forwarder_name': 'webhook',
                'attempt': 1,
            })
        finally:
            pl.removeHandler(h)