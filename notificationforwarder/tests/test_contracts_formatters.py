"""
Contract tests for notificationforwarder formatters.

This file covers the format_event behavior of email, syslog, example,
and other built-in formatters.
"""
import os
import sys
from types import SimpleNamespace

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
# Builtin formatter tests
# ============================================================================

class TestBuiltinFormatters:
    def test_email_formatter_html_and_text(self, setup):
        """Email formatter produces html and text payload with mail summary."""
        forwarder = _new_forwarder("email")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "HOSTNAME": "mailhost",
            "HOSTADDRESS": "127.0.0.1",
            "NOTIFICATIONTYPE": "PROBLEM",
            "SERVICEDESC": "smtp",
            "SERVICESTATE": "CRITICAL",
            "SERVICEOUTPUT": "smtp down",
        })
        formatter.format_event(event)
        
        assert event.summary == "mail"
        assert set(event.payload) == {"html", "text", "subject"}
        assert "mailhost" in event.payload["html"]
        assert "smtp" in event.payload["text"]

    def test_syslog_formatter_host_event(self, setup):
        """Syslog formatter produces host:state summary and output payload."""
        forwarder = _new_forwarder("syslog")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "HOSTNAME": "syshost",
            "HOSTSTATE": "DOWN",
            "HOSTOUTPUT": "host down",
        })
        formatter.format_event(event)
        
        assert event.summary == "host: syshost, state: DOWN"
        assert event.payload == "host: syshost, state: DOWN, output: host down"

    def test_rabbitmq_formatter_queue_event(self, setup):
        """RabbitMQ formatter produces queue payload with host and state."""
        forwarder = _new_forwarder("rabbitmq")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "HOSTNAME": "queuehost",
            "NOTIFICATIONTYPE": "PROBLEM",
            "HOSTSTATE": "DOWN",
            "HOSTOUTPUT": "queue down",
        })
        formatter.format_event(event)
        
        assert event.summary == str(event.payload[0])
        assert event.payload[0]["host_name"] == "queuehost"
        assert event.payload[0]["state"] == "DOWN"

    def test_example_formatter_with_signature(self, setup):
        """Example formatter produces summary, payload, and timestamp."""
        forwarder = _new_forwarder("example")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "description": "hello world",
            "signature": "sig-1",
        })
        formatter.format_event(event)

        assert event.summary == "sum: hello world"
        assert event.payload["description"] == "hello world"
        assert event.payload["signature"] == "sig-1"
        assert "timestamp" in event.payload


# ============================================================================
# Email formatter edge tests
# ============================================================================

class TestEmailFormatterEdges:
    def test_host_only_notification(self, setup):
        """Email formatter uses host templates for host-only events."""
        forwarder = _new_forwarder("email")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "HOSTNAME": "myhost",
            "HOSTSTATE": "DOWN",
            "HOSTOUTPUT": "host unreachable",
        })
        formatter.format_event(event)

        assert "myhost" in event.payload["html"]
        assert "myhost" in event.payload["text"]
        assert "DOWN" in event.payload["text"]

    def test_acknowledgement_block(self, setup):
        """Email formatter renders ACKAUTHOR and ACKCOMMENT for acknowledgements."""
        forwarder = _new_forwarder("email")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "HOSTNAME": "myhost",
            "SERVICEDESC": "http",
            "SERVICESTATE": "CRITICAL",
            "SERVICEOUTPUT": "down",
            "NOTIFICATIONTYPE": "ACKNOWLEDGEMENT",
            "ACKAUTHOR": "admin",
            "ACKCOMMENT": "investigating",
        })
        formatter.format_event(event)

        text = event.payload["text"]
        assert "admin" in text
        assert "investigating" in text

    def test_notification_comment(self, setup):
        """Email formatter renders NOTIFICATIONCOMMENT for non-ACK notifications."""
        forwarder = _new_forwarder("email")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "HOSTNAME": "myhost",
            "SERVICEDESC": "http",
            "SERVICESTATE": "CRITICAL",
            "SERVICEOUTPUT": "down",
            "NOTIFICATIONTYPE": "PROBLEM",
            "NOTIFICATIONCOMMENT": "known issue",
        })
        formatter.format_event(event)

        text = event.payload["text"]
        assert "known issue" in text

    def test_missing_optional_macros(self, setup):
        """Email formatter handles missing LONGSERVICEOUTPUT and CONTACTEMAIL."""
        forwarder = _new_forwarder("email")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "HOSTNAME": "myhost",
            "SERVICEDESC": "http",
            "SERVICESTATE": "OK",
            "SERVICEOUTPUT": "all good",
        })
        formatter.format_event(event)

        assert event.payload["subject"] == "thesubtschek"
        assert event.summary == "mail"


# ============================================================================
# Syslog formatter edge tests
# ============================================================================

class TestSyslogFormatterEdges:
    def test_host_event(self, setup):
        """Syslog formatter uses host macros for host-only events."""
        forwarder = _new_forwarder("syslog")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "HOSTNAME": "syshost",
            "HOSTSTATE": "DOWN",
            "HOSTOUTPUT": "host unreachable",
        })
        formatter.format_event(event)

        assert "syshost" in event.payload
        assert "DOWN" in event.payload
        assert "host unreachable" in event.payload


# ============================================================================
# Own-module contract smoke tests (agent templates)
# ============================================================================
# AI-AGENT TEMPLATE: when a user says "I need a formatter for Ticket System XY",
# copy this structure, replace the external mock, keep the contract assertions.

class TestOwnFormatterSmoke:
    def test_own_formatter_produces_payload_and_summary(self, setup):
        """
        AI-AGENT TEMPLATE: Own formatter contract smoke.
        When implementing a new formatter, ensure format_event sets both
        event.payload (dict with data for the forwarder) and event.summary
        (human-readable string for logging).
        """
        # Use the vong formatter as an example "own" formatter loaded from pythonpath
        from notificationforwarder.vong.formatter import VongFormatter

        formatter = VongFormatter()
        event = FormattedEvent({
            "HOSTNAME": "myhost",
            "SERVICEDESC": "myservice",
            "SERVICESTATE": "WARNING",
            "SERVICEOUTPUT": "check output",
        })

        formatter.format_event(event)

        # Contract: payload must be a dict
        assert isinstance(event.payload, dict)
        # Contract: summary must be a non-empty string
        assert isinstance(event.summary, str)
        assert len(event.summary) > 0
        # Contract: payload contains host_name
        assert "host_name" in event.payload
        assert event.payload["host_name"] == "myhost"

    def test_own_formatter_host_only_event(self, setup):
        """
        AI-AGENT TEMPLATE: Own formatter must handle host-only events
        (no SERVICEDESC) gracefully.
        """
        from notificationforwarder.vong.formatter import VongFormatter

        formatter = VongFormatter()
        event = FormattedEvent({
            "HOSTNAME": "myhost",
            "HOSTSTATE": "DOWN",
        })

        formatter.format_event(event)

        assert isinstance(event.payload, dict)
        assert event.payload["host_name"] == "myhost"
        assert isinstance(event.summary, str)

    def test_multiline_output(self, setup):
        """Syslog formatter preserves multiline output in a single line."""
        forwarder = _new_forwarder("syslog")
        formatter = forwarder.new_formatter()
        event = _formatted_event({
            "HOSTNAME": "syshost",
            "SERVICEDESC": "check",
            "SERVICESTATE": "WARNING",
            "SERVICEOUTPUT": "line1\nline2\nline3",
        })
        formatter.format_event(event)

        assert "line1\nline2\nline3" in event.payload