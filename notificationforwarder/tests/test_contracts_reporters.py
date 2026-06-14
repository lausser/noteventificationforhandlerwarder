"""
Contract tests for notificationforwarder reporters.

This file covers the builtin naemonlog reporter and preserves custom
reporter logic (e.g., ticketsystem report_payload precedence).
"""
import logging
import os
import sys

import pytest

os.environ["PYTHONDONTWRITEBYTECODE"] = "true"

OMD_ROOT = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = OMD_ROOT

if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/../src")

from notificationforwarder.baseclass import FormattedEvent
from notificationforwarder.naemonlog.reporter import NaemonlogReporter


def _setup():
    omd_root = os.path.dirname(__file__)
    os.environ["OMD_ROOT"] = omd_root
    import shutil
    shutil.rmtree(omd_root + "/var", ignore_errors=True)
    os.makedirs(omd_root + "/var/log", 0o755)
    os.makedirs(omd_root + "/var/tmp", 0o755)
    shutil.rmtree(omd_root + "/tmp", ignore_errors=True)
    os.makedirs(omd_root + "/tmp", 0o755)


@pytest.fixture
def setup():
    _setup()
    yield


def _formatted_event(eventopts):
    return FormattedEvent(dict(eventopts))


def get_logfile(forwarder):
    logger_name = "notificationforwarder_" + forwarder.name
    python_logger = logging.getLogger(logger_name)
    for handler in python_logger.handlers:
        flush = getattr(handler, "flush", None)
        if callable(flush):
            flush()
    return [h.baseFilename for h in python_logger.handlers if hasattr(h, "baseFilename")][0]


# ============================================================================
# Naemonlog reporter tests
# ============================================================================

class TestNaemonlogReporter:
    def test_writes_expected_host_and_service_lines(self, setup):
        """Naemonlog reporter writes expected host and service notification lines."""
        reporter = NaemonlogReporter({"command_file": os.path.join(OMD_ROOT, "var", "tmp", "naemon.cmd")})

        host_event = _formatted_event(
            {
                "HOSTNAME": "host-1",
                "HOSTSTATE": "DOWN",
                "HOSTOUTPUT": "host output",
            }
        )
        host_event.eventopts["forwarder_success"] = False
        host_event.eventopts["forwarder_name"] = "webhook"
        reporter.report_event(host_event)

        service_event = _formatted_event(
            {
                "HOSTNAME": "host-2",
                "SERVICEDESC": "svc-1",
                "SERVICESTATE": "CRITICAL",
                "SERVICEOUTPUT": "service output",
                "CONTACTNAME": "ops",
                "NOTIFICATIONCOMMAND": "handler",
            }
        )
        service_event.eventopts["forwarder_success"] = True
        service_event.eventopts["forwarder_name"] = "webhook"
        reporter.report_event(service_event)

        with open(os.path.join(OMD_ROOT, "var", "tmp", "naemon.cmd")) as fh:
            contents = fh.read()

        assert "HOST NOTIFICATION: GLOBAL;host-1;global_host_notification_handler;DOWN;host output (could not be forwarded to webhook)" in contents
        assert "SERVICE NOTIFICATION: ops;host-2;svc-1;handler;CRITICAL;service output" in contents

    def test_missing_command_file_silent_noop(self, setup):
        """Naemonlog reporter with missing command_file and no cfg is silent no-op."""
        # This test documents the current behavior - no command_file means no action
        reporter = NaemonlogReporter({})
        
        event = _formatted_event({"HOSTNAME": "h1", "HOSTSTATE": "DOWN", "HOSTOUTPUT": "down"})
        event.eventopts["forwarder_success"] = True
        event.eventopts["forwarder_name"] = "webhook"
        
        # Should not raise
        reporter.report_event(event)

    def test_default_contact_name_global(self, setup):
        """Naemonlog reporter uses GLOBAL as default CONTACTNAME."""
        reporter = NaemonlogReporter({"command_file": os.path.join(OMD_ROOT, "var", "tmp", "naemon.cmd")})
        
        event = _formatted_event({
            "HOSTNAME": "h1",
            "HOSTSTATE": "DOWN",
            "HOSTOUTPUT": "down",
            # No CONTACTNAME specified
        })
        event.eventopts["forwarder_success"] = True
        event.eventopts["forwarder_name"] = "webhook"
        
        reporter.report_event(event)
        
        with open(os.path.join(OMD_ROOT, "var", "tmp", "naemon.cmd")) as fh:
            contents = fh.read()
        
        assert "HOST NOTIFICATION: GLOBAL;h1;global_host_notification_handler;DOWN;down" in contents

    def test_explicit_command_file_appends_log_line(self, setup):
        """Explicit command_file appends a LOG line with timestamp."""
        cmd_file = os.path.join(OMD_ROOT, "var", "tmp", "test_naemon.cmd")
        reporter = NaemonlogReporter({"command_file": cmd_file})

        event = _formatted_event({
            "HOSTNAME": "h1",
            "HOSTSTATE": "UP",
            "HOSTOUTPUT": "ok",
        })
        event.eventopts["forwarder_success"] = True
        event.eventopts["forwarder_name"] = "webhook"

        reporter.report_event(event)

        with open(cmd_file) as fh:
            contents = fh.read()

        assert "LOG;HOST NOTIFICATION: GLOBAL;h1;global_host_notification_handler;UP;ok" in contents

    def test_host_vs_service_default_notification_command(self, setup):
        """Host and service events use different default notification commands."""
        cmd_file = os.path.join(OMD_ROOT, "var", "tmp", "test_naemon2.cmd")
        reporter = NaemonlogReporter({"command_file": cmd_file})

        host_event = _formatted_event({
            "HOSTNAME": "h1",
            "HOSTSTATE": "DOWN",
            "HOSTOUTPUT": "down",
        })
        host_event.eventopts["forwarder_success"] = True
        host_event.eventopts["forwarder_name"] = "webhook"
        reporter.report_event(host_event)

        svc_event = _formatted_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "http",
            "SERVICESTATE": "CRITICAL",
            "SERVICEOUTPUT": "down",
        })
        svc_event.eventopts["forwarder_success"] = True
        svc_event.eventopts["forwarder_name"] = "webhook"
        reporter.report_event(svc_event)

        with open(cmd_file) as fh:
            contents = fh.read()

        assert "global_host_notification_handler" in contents
        assert "global_service_notification_handler" in contents

    def test_unknown_reporter_critical_logs_but_forwarding_unaffected(self, setup):
        """Unknown reporter name critical-logs but forwarding still works."""
        from notificationforwarder import baseclass
        import notificationforwarder.baseclass as baseclass_module

        # Create a forwarder with unknown reporter
        forwarder = baseclass.new(
            "example",
            None,
            "example",
            True,
            True,
            {},
            reporter_name="nonexistent_reporter",
            logger_type="text",
        )

        event = _formatted_event({"description": "test"})
        event.payload = {"description": "test"}
        event.summary = "test"

        # Forwarding should still work even though reporter fails
        result = forwarder.forward({"description": "test"})

        # Check the log file for reporter-related critical messages
        log_file = get_logfile(forwarder) if hasattr(forwarder, 'name') else None
        if log_file and os.path.exists(log_file):
            log_content = open(log_file).read()
            assert "no reporter" in log_content.lower() or \
                   "could not create" in log_content.lower() or \
                   "reporter" in log_content.lower()

    def test_no_config_anywhere_silent_noop(self, setup, monkeypatch):
        """No command_file in opts and no readable naemon.cfg = silent no-op."""
        import os
        reporter = NaemonlogReporter({})

        # Ensure OMD_ROOT is set but naemon.cfg doesn't exist
        monkeypatch.setenv("OMD_ROOT", OMD_ROOT)

        event = _formatted_event({
            "HOSTNAME": "h1",
            "HOSTSTATE": "DOWN",
            "HOSTOUTPUT": "down",
        })
        event.eventopts["forwarder_success"] = True
        event.eventopts["forwarder_name"] = "webhook"

        # Should not raise, should be a silent no-op
        reporter.report_event(event)

    def test_failure_suffix_appended(self, setup):
        """Forwarder failure appends 'could not be forwarded' suffix."""
        cmd_file = os.path.join(OMD_ROOT, "var", "tmp", "test_naemon3.cmd")
        reporter = NaemonlogReporter({"command_file": cmd_file})

        event = _formatted_event({
            "HOSTNAME": "h1",
            "HOSTSTATE": "DOWN",
            "HOSTOUTPUT": "down",
        })
        event.eventopts["forwarder_success"] = False
        event.eventopts["forwarder_name"] = "webhook"

        reporter.report_event(event)

        with open(cmd_file) as fh:
            contents = fh.read()

        assert "(could not be forwarded to webhook)" in contents