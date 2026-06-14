"""
Contract tests for notificationforwarder forwarders.

This file covers the submit/forward paths of email, syslog, and telegram
forwarders using mocks for external transport libraries.
"""
import json
import logging
import os
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
import socket

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
import notificationforwarder.email.forwarder as email_module
import notificationforwarder.syslog.forwarder as syslog_module
import notificationforwarder.telegram.forwarder as telegram_module


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
# Email forwarder tests
# ============================================================================

class TestEmailForwarder:
    def test_smtp_success_with_html_and_text(self, setup, monkeypatch):
        """Email forwarder sends correct MIME parts when html+text provided."""
        forwarder = email_module.EmailForwarder({
            "sender": "test@example.com",
            "recipient": "dest@example.com",
            "smtp_server": "localhost",
            "smtp_port": 25,
        })

        mock_smtp = MagicMock()
        monkeypatch.setattr(email_module.smtplib, "SMTP", lambda *args: mock_smtp)

        event = _formatted_event({"description": "test"})
        event.payload = {
            "subject": "Test Subject",
            "html": "<h1>HTML Content</h1>",
            "text": "Text Content",
        }
        event.summary = "Test Summary"

        result = forwarder.submit(event)

        assert result is True
        mock_smtp.sendmail.assert_called_once()
        mock_smtp.quit.assert_called_once()

    def test_html_only_payload(self, setup, monkeypatch):
        """Email forwarder sends HTML-only MIME part."""
        forwarder = email_module.EmailForwarder({
            "sender": "test@example.com",
            "recipient": "dest@example.com",
            "smtp_server": "localhost",
            "smtp_port": 25,
        })

        mock_smtp = MagicMock()
        monkeypatch.setattr(email_module.smtplib, "SMTP", lambda *args: mock_smtp)

        event = _formatted_event({"description": "test"})
        event.payload = {
            "subject": "Test Subject",
            "html": "<h1>HTML Only</h1>",
        }
        event.summary = "Test Summary"

        result = forwarder.submit(event)
        assert result is True
        mock_smtp.sendmail.assert_called_once()

    def test_text_only_payload(self, setup, monkeypatch):
        """Email forwarder sends text-only MIME part."""
        forwarder = email_module.EmailForwarder({
            "sender": "test@example.com",
            "recipient": "dest@example.com",
            "smtp_server": "localhost",
            "smtp_port": 25,
        })

        mock_smtp = MagicMock()
        monkeypatch.setattr(email_module.smtplib, "SMTP", lambda *args: mock_smtp)

        event = _formatted_event({"description": "test"})
        event.payload = {
            "subject": "Test Subject",
            "text": "Plain Text Only",
        }
        event.summary = "Test Summary"

        result = forwarder.submit(event)
        assert result is True
        mock_smtp.sendmail.assert_called_once()

    def test_missing_body_fallback(self, setup, monkeypatch):
        """Email forwarder sends fallback message when no html or text."""
        forwarder = email_module.EmailForwarder({
            "sender": "test@example.com",
            "recipient": "dest@example.com",
            "smtp_server": "localhost",
            "smtp_port": 25,
        })

        mock_smtp = MagicMock()
        monkeypatch.setattr(email_module.smtplib, "SMTP", lambda *args: mock_smtp)

        event = _formatted_event({"description": "test"})
        event.payload = {
            "subject": "Test Subject",
        }
        event.summary = "Test Summary"

        result = forwarder.submit(event)
        assert result is True
        mock_smtp.sendmail.assert_called_once()

    def test_smtp_exception_returns_false(self, setup, monkeypatch):
        """Email forwarder returns False on SMTP exception."""
        import smtplib

        forwarder = email_module.EmailForwarder({
            "sender": "test@example.com",
            "recipient": "dest@example.com",
            "smtp_server": "localhost",
            "smtp_port": 25,
        })

        def raise_smtp(*args):
            raise smtplib.SMTPException("Connection refused")

        monkeypatch.setattr(email_module.smtplib, "SMTP", raise_smtp)

        event = _formatted_event({"description": "test"})
        event.payload = {
            "subject": "Test Subject",
            "html": "<h1>Test</h1>",
        }
        event.summary = "Test Summary"

        result = forwarder.submit(event)
        assert result is False

    def test_failure_spools_non_heartbeat(self, setup, monkeypatch):
        """Email forwarder spools event on failure for non-heartbeat."""
        import smtplib

        forwarder = _new_forwarder(
            "example",
            forwarder_name="email",
            forwarder_opts={
                "sender": "test@example.com",
                "recipient": "dest@example.com",
                "smtp_server": "localhost",
                "smtp_port": 25,
            },
        )

        def raise_smtp(*args):
            raise smtplib.SMTPException("Connection refused")

        monkeypatch.setattr(email_module.smtplib, "SMTP", raise_smtp)

        spooled = []
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or True)

        event = {"description": "needs retry"}
        forwarder.forward(event)

        assert spooled and spooled[0]["description"] == "needs retry"


# ============================================================================
# Syslog forwarder tests
# ============================================================================

class TestSyslogForwarder:
    def test_facility_normalization(self, setup, monkeypatch):
        """Syslog facility local0 and log_local0 resolve to same value."""
        monkeypatch.setattr(logging.handlers, "SysLogHandler", MagicMock())

        forwarder1 = syslog_module.SyslogForwarder({
            "server": "localhost",
            "port": 514,
            "facility": "local0",
            "priority": "info",
            "protocol": "udp",
        })

        forwarder2 = syslog_module.SyslogForwarder({
            "server": "localhost",
            "port": 514,
            "facility": "log_local0",
            "priority": "info",
            "protocol": "udp",
        })

        assert forwarder1.facility == forwarder2.facility

    def test_invalid_facility_fallback(self, setup, monkeypatch):
        """Syslog forwarder falls back to LOG_DAEMON for unknown facility."""
        monkeypatch.setattr(logging.handlers, "SysLogHandler", MagicMock())

        forwarder = syslog_module.SyslogForwarder({
            "server": "localhost",
            "port": 514,
            "facility": "unknown_facility",
            "priority": "info",
            "protocol": "udp",
        })

        assert forwarder.facility == logging.handlers.SysLogHandler.LOG_DAEMON

    def test_priority_normalization(self, setup, monkeypatch):
        """Syslog priority info and log_info resolve to same value."""
        monkeypatch.setattr(logging.handlers, "SysLogHandler", MagicMock())

        forwarder1 = syslog_module.SyslogForwarder({
            "server": "localhost",
            "port": 514,
            "facility": "local0",
            "priority": "info",
            "protocol": "udp",
        })

        forwarder2 = syslog_module.SyslogForwarder({
            "server": "localhost",
            "port": 514,
            "facility": "local0",
            "priority": "log_info",
            "protocol": "udp",
        })

        assert forwarder1.priority == forwarder2.priority

    def test_invalid_priority_fallback(self, setup, monkeypatch):
        """Syslog forwarder falls back to LOG_INFO for unknown priority."""
        monkeypatch.setattr(logging.handlers, "SysLogHandler", MagicMock())

        forwarder = syslog_module.SyslogForwarder({
            "server": "localhost",
            "port": 514,
            "facility": "local0",
            "priority": "unknown_priority",
            "protocol": "udp",
        })

        assert forwarder.priority == logging.handlers.SysLogHandler.LOG_INFO

    def test_submit_exception_returns_false(self, setup, monkeypatch):
        """Syslog forwarder returns False on handler exception."""
        mock_handler = MagicMock()
        mock_handler.log.side_effect = Exception("Syslog error")
        monkeypatch.setattr(logging.handlers, "SysLogHandler", MagicMock(return_value=mock_handler))

        forwarder = syslog_module.SyslogForwarder({
            "server": "localhost",
            "port": 514,
            "facility": "local0",
            "priority": "info",
            "protocol": "udp",
        })

        event = _formatted_event({"description": "test"})
        event.payload = "Test syslog message"
        event.summary = "Test Summary"

        result = forwarder.submit(event)
        assert result is False


# ============================================================================
# Telegram forwarder tests
# ============================================================================

class TestTelegramForwarder:
    def test_submit_success(self, setup, monkeypatch):
        """Telegram forwarder returns True on successful API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'

        monkeypatch.setattr(telegram_module.requests, "get", lambda *args, **kwargs: mock_response)

        forwarder = telegram_module.TelegramForwarder({
            "bot_token": "test_token",
            "chat_id": "12345",
        })

        event = _formatted_event({"description": "test"})
        event.payload = "Test message"
        event.summary = "Test Summary"

        result = forwarder.submit_one(event)
        assert result is True

    def test_submit_http_failure(self, setup, monkeypatch):
        """Telegram forwarder returns False on non-200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        monkeypatch.setattr(telegram_module.requests, "get", lambda *args, **kwargs: mock_response)

        forwarder = telegram_module.TelegramForwarder({
            "bot_token": "test_token",
            "chat_id": "12345",
        })

        event = _formatted_event({"description": "test"})
        event.payload = "Test message"
        event.summary = "Test Summary"

        result = forwarder.submit_one(event)
        assert result is False

    def test_submit_timeout_status(self, setup, monkeypatch):
        """Telegram forwarder returns False on timeout status codes."""
        for status_code in [408, 504]:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.text = "Timeout"

            monkeypatch.setattr(telegram_module.requests, "get", lambda *args, **kwargs: mock_response)

            forwarder = telegram_module.TelegramForwarder({
                "bot_token": "test_token",
                "chat_id": "12345",
            })

            event = _formatted_event({"description": "test"})
            event.payload = "Test message"
            event.summary = "Test Summary"

            result = forwarder.submit_one(event)
            assert result is False

    def test_list_payload_all_success(self, setup, monkeypatch):
        """Telegram forwarder returns True when all list items succeed."""
        forwarder = telegram_module.TelegramForwarder({
            "bot_token": "test_token",
            "chat_id": "12345",
        })

        monkeypatch.setattr(forwarder, "submit_one", lambda event: True)

        events = [
            _formatted_event({"description": "event1"}),
            _formatted_event({"description": "event2"}),
        ]
        events[0].payload = "msg1"
        events[0].summary = "summary1"
        events[1].payload = "msg2"
        events[1].summary = "summary2"

        result = forwarder.submit(events)
        assert result is True

    def test_list_payload_partial_failure(self, setup, monkeypatch):
        """Telegram forwarder returns False when any list item fails."""
        forwarder = telegram_module.TelegramForwarder({
            "bot_token": "test_token",
            "chat_id": "12345",
        })

        call_count = [0]

        def mock_submit_one(event):
            call_count[0] += 1
            return call_count[0] == 1  # First succeeds, second fails

        monkeypatch.setattr(forwarder, "submit_one", mock_submit_one)

        events = [
            _formatted_event({"description": "event1"}),
            _formatted_event({"description": "event2"}),
        ]
        events[0].payload = "msg1"
        events[0].summary = "summary1"
        events[1].payload = "msg2"
        events[1].summary = "summary2"

        result = forwarder.submit(events)
        assert result is False

    def test_heartbeat_no_spool(self, setup, monkeypatch):
        """Telegram forwarder does not spool heartbeat events on failure."""
        forwarder = telegram_module.TelegramForwarder({
            "bot_token": "test_token",
            "chat_id": "12345",
        })

        monkeypatch.setattr(forwarder, "submit_one", lambda event: False)

        event = {"description": "heartbeat"}

        spooled = []
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or True)

        # Mock format_event to return a formatted event with is_heartbeat=True
        mock_formatted = _formatted_event({"description": "heartbeat"})
        mock_formatted.is_heartbeat = True
        monkeypatch.setattr(forwarder, "format_event", lambda raw: mock_formatted)

        forwarder.forward(event)

        # Heartbeat events should not be spooled
        assert len(spooled) == 0

    def test_failure_spools_non_heartbeat(self, setup, monkeypatch):
        """Telegram forwarder spools non-heartbeat events on failure."""
        forwarder = _new_forwarder(
            "example",
            forwarder_name="telegram",
            forwarder_opts={
                "bot_token": "test_token",
                "chat_id": "12345",
            },
        )

        monkeypatch.setattr(forwarder, "submit_one", lambda event: False)

        event = {"description": "normal"}

        spooled = []
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or True)

        # Mock format_event to return a formatted event without heartbeat
        mock_formatted = _formatted_event({"description": "normal"})
        mock_formatted.is_heartbeat = False
        mock_formatted.payload = {"data": "test"}
        mock_formatted.summary = "test summary"
        monkeypatch.setattr(forwarder, "format_event", lambda raw: mock_formatted)

        forwarder.forward(event)

        assert len(spooled) == 1


# ============================================================================
# Webhook forwarder tests (from test_builtin_plugins_focus.py)
# ============================================================================

class TestWebhookForwarder:
    def test_submit_one_supports_modes_and_overrides(self, setup, monkeypatch):
        """Webhook forwarder supports json, form, and raw modes with overrides."""
        import notificationforwarder.webhook.forwarder as webhook_module
        
        cases = [
            ("json", {"description": "json payload"}, "json", "application/json"),
            ("form", {"description": "form payload"}, "data", "application/x-www-form-urlencoded"),
            ("raw", {"description": "raw payload"}, "data", "text/xml"),
        ]

        for mode, payload, expected_key, content_type in cases:
            forwarder = _new_forwarder(
                "example",
                forwarder_name="webhook",
                forwarder_opts={
                    "url": "http://example.invalid/api",
                    "username": "demo",
                    "password": "secret",
                    "headers": {"X-Base": "base"},
                },
            )

            captured = []

            def fake_post(url, **kwargs):
                captured.append((url, kwargs))
                return SimpleNamespace(status_code=200, text="ok", reason="ok")

            monkeypatch.setattr(webhook_module.requests, "post", fake_post)

            event = _formatted_event({"description": payload["description"]})
            event.payload = payload if mode != "raw" else [payload]
            event.summary = payload["description"]
            event.forwarderopts["mode"] = mode
            event.forwarderopts["url"] = "http://example.invalid/override"
            event.forwarderopts["headers"] = json.dumps({"X-Event": mode})

            assert forwarder.submit_one(event) is True
            url, kwargs = captured.pop()
            assert url == "http://example.invalid/override"
            assert expected_key in kwargs
            assert kwargs[expected_key]
            assert kwargs["headers"]["Content-Type"] == content_type
            assert kwargs["headers"]["X-Base"] == "base"
            assert kwargs["headers"]["X-Event"] == mode
            assert kwargs["auth"].username == "demo"
            assert kwargs["auth"].password == "secret"

        event = _formatted_event({"description": "broken"})
        event.payload = {"description": "broken"}
        event.summary = "broken"
        event.forwarderopts["mode"] = "unsupported"
        assert forwarder.submit_one(event) is False

    def test_forward_failure_spools_and_handles_spool_errors(self, setup, monkeypatch):
        """Webhook forwarder spools on failure and handles spool errors."""
        import notificationforwarder.webhook.forwarder as webhook_module
        
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        monkeypatch.setattr(
            webhook_module.requests,
            "post",
            lambda *args, **kwargs: SimpleNamespace(status_code=500, text="nope", reason="bad"),
        )

        spooled = []
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or True)
        forwarder.forward({"description": "needs retry"})
        assert spooled and spooled[0]["description"] == "needs retry"

        forwarder2 = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )
        monkeypatch.setattr(
            webhook_module.requests,
            "post",
            lambda *args, **kwargs: SimpleNamespace(status_code=500, text="nope", reason="bad"),
        )
        monkeypatch.setattr(forwarder2, "spool", lambda raw_event: False)
        forwarder2.forward({"description": "cannot persist"})


# ============================================================================
# Webhook extended tests
# ============================================================================

class TestWebhookExtended:
    def test_accepted_created_status(self, setup, monkeypatch):
        """201 and 202 status codes are treated as success."""
        import notificationforwarder.webhook.forwarder as webhook_module

        for status_code in [201, 202]:
            forwarder = _new_forwarder(
                "example",
                forwarder_name="webhook",
                forwarder_opts={"url": "http://example.invalid/api"},
            )

            captured = []

            def fake_post(url, **kwargs):
                captured.append((url, kwargs))
                return SimpleNamespace(status_code=status_code, text="created", reason="created")

            monkeypatch.setattr(webhook_module.requests, "post", fake_post)

            event = _formatted_event({"description": "test"})
            event.payload = {"description": "test"}
            event.summary = "test"

            assert forwarder.submit_one(event) is True

    def test_insecure_verify_disabled(self, setup, monkeypatch):
        """insecure=yes passes verify=False to requests."""
        import notificationforwarder.webhook.forwarder as webhook_module

        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={
                "url": "http://example.invalid/api",
                "insecure": "yes",
            },
        )

        captured = []

        def fake_post(url, **kwargs):
            captured.append(kwargs)
            return SimpleNamespace(status_code=200, text="ok", reason="ok")

        monkeypatch.setattr(webhook_module.requests, "post", fake_post)

        event = _formatted_event({"description": "test"})
        event.payload = {"description": "test"}
        event.summary = "test"

        forwarder.submit_one(event)
        assert captured[0].get("verify") is False

    def test_url_override_from_event(self, setup, monkeypatch):
        """URL override from event.forwarderopts takes precedence."""
        import notificationforwarder.webhook.forwarder as webhook_module

        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/original"},
        )

        captured = []

        def fake_post(url, **kwargs):
            captured.append(url)
            return SimpleNamespace(status_code=200, text="ok", reason="ok")

        monkeypatch.setattr(webhook_module.requests, "post", fake_post)

        event = _formatted_event({"description": "test"})
        event.payload = {"description": "test"}
        event.summary = "test"
        event.forwarderopts["url"] = "http://example.invalid/override"

        forwarder.submit_one(event)
        assert captured[0] == "http://example.invalid/override"

    def test_headers_merge(self, setup, monkeypatch):
        """Base headers and per-event headers are merged correctly."""
        import notificationforwarder.webhook.forwarder as webhook_module
        import json as json_mod

        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={
                "url": "http://example.invalid/api",
                "headers": {"X-Base": "base_value"},
            },
        )

        captured = []

        def fake_post(url, **kwargs):
            captured.append(kwargs)
            return SimpleNamespace(status_code=200, text="ok", reason="ok")

        monkeypatch.setattr(webhook_module.requests, "post", fake_post)

        event = _formatted_event({"description": "test"})
        event.payload = {"description": "test"}
        event.summary = "test"
        event.forwarderopts["headers"] = json_mod.dumps({"X-Event": "event_value"})

        forwarder.submit_one(event)
        headers = captured[0]["headers"]
        assert headers["X-Base"] == "base_value"
        assert headers["X-Event"] == "event_value"

    def test_timeout_exception_returns_false(self, setup, monkeypatch):
        """Timeout exception during POST returns False."""
        import notificationforwarder.webhook.forwarder as webhook_module

        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        def raise_timeout(*args, **kwargs):
            raise webhook_module.requests.exceptions.Timeout("timed out")

        monkeypatch.setattr(webhook_module.requests, "post", raise_timeout)

        event = _formatted_event({"description": "test"})
        event.payload = {"description": "test"}
        event.summary = "test"

        result = forwarder.submit_one(event)
        assert result is False

    def test_content_type_header_precedence(self, setup, monkeypatch):
        """Existing Content-Type header is not overwritten by mode default."""
        import notificationforwarder.webhook.forwarder as webhook_module
        import json as json_mod

        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        captured = []

        def fake_post(url, **kwargs):
            captured.append(kwargs)
            return SimpleNamespace(status_code=200, text="ok", reason="ok")

        monkeypatch.setattr(webhook_module.requests, "post", fake_post)

        event = _formatted_event({"description": "test"})
        event.payload = {"description": "test"}
        event.summary = "test"
        event.forwarderopts["mode"] = "json"
        event.forwarderopts["headers"] = json_mod.dumps({"Content-Type": "application/custom+json"})

        forwarder.submit_one(event)
        assert captured[0]["headers"]["Content-Type"] == "application/custom+json"

    def test_url_mutation_side_effect(self, setup, monkeypatch):
        """URL override from event permanently mutates self.url."""
        import notificationforwarder.webhook.forwarder as webhook_module

        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/original"},
        )

        urls_captured = []

        def fake_post(url, **kwargs):
            urls_captured.append(url)
            return SimpleNamespace(status_code=200, text="ok", reason="ok")

        monkeypatch.setattr(webhook_module.requests, "post", fake_post)

        # First event with URL override
        event1 = _formatted_event({"description": "test1"})
        event1.payload = {"description": "test1"}
        event1.summary = "test1"
        event1.forwarderopts["url"] = "http://example.invalid/override"
        forwarder.submit_one(event1)

        # Second event without URL override - uses mutated URL
        event2 = _formatted_event({"description": "test2"})
        event2.payload = {"description": "test2"}
        event2.summary = "test2"
        forwarder.submit_one(event2)

        assert urls_captured[0] == "http://example.invalid/override"
        assert urls_captured[1] == "http://example.invalid/override"  # Mutated

    def test_header_case_insensitive_merge(self, setup, monkeypatch):
        """Content-type in various cases prevents default Content-Type from being added."""
        import notificationforwarder.webhook.forwarder as webhook_module
        import json as json_mod

        for variant in ["Content-type", "content-Type", "CONTENT-TYPE"]:
            forwarder = _new_forwarder(
                "example",
                forwarder_name="webhook",
                forwarder_opts={"url": "http://example.invalid/api"},
            )

            captured = []

            def fake_post(url, **kwargs):
                captured.append(kwargs)
                return SimpleNamespace(status_code=200, text="ok", reason="ok")

            monkeypatch.setattr(webhook_module.requests, "post", fake_post)

            event = _formatted_event({"description": "test"})
            event.payload = {"description": "test"}
            event.summary = "test"
            event.forwarderopts["mode"] = "json"
            event.forwarderopts["headers"] = json_mod.dumps({variant: "text/plain"})

            forwarder.submit_one(event)
            assert captured[0]["headers"][variant] == "text/plain"

    def test_raw_mode_list_payload(self, setup, monkeypatch):
        """Raw mode with list payload sends json.dumps(list)."""
        import notificationforwarder.webhook.forwarder as webhook_module
        import json as json_mod

        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        captured = []

        def fake_post(url, **kwargs):
            captured.append(kwargs)
            return SimpleNamespace(status_code=200, text="ok", reason="ok")

        monkeypatch.setattr(webhook_module.requests, "post", fake_post)

        event = _formatted_event({"description": "test"})
        event.payload = [{"key": "val1"}, {"key": "val2"}]
        event.summary = "test"
        event.forwarderopts["mode"] = "raw"

        forwarder.submit_one(event)
        assert captured[0]["data"] == json_mod.dumps([{"key": "val1"}, {"key": "val2"}])


# ============================================================================
# Own-module contract smoke tests (agent templates)
# ============================================================================
# AI-AGENT TEMPLATE: when a user says "I need a forwarder for Ticket System XY",
# copy this structure, replace the external mock, keep the contract assertions.

class TestOwnForwarderSmoke:
    def test_own_forwarder_submit_success(self, setup, monkeypatch):
        """
        AI-AGENT TEMPLATE: Own forwarder contract smoke.
        When implementing a new forwarder, ensure submit() returns True on
        success and False on failure. The forwarder receives a FormattedEvent
        with .payload and .summary already set by the formatter.
        """
        # Create a minimal "own" forwarder using the example forwarder
        from notificationforwarder.example.forwarder import ExampleForwarder

        forwarder = ExampleForwarder({"path": "/tmp/test_smoke.txt"})

        event = _formatted_event({"description": "smoke test"})
        event.payload = {"description": "smoke test", "signature": "abc123"}
        event.summary = "smoke test summary"

        result = forwarder.submit(event)

        # Contract: submit returns a boolean
        assert isinstance(result, bool)

    def test_own_forwarder_failure_spools_for_non_heartbeat(self, setup, monkeypatch):
        """
        AI-AGENT TEMPLATE: Own forwarder failure path.
        When submit() fails for a non-heartbeat event, the base class
        should spool the raw event for retry.
        """
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        # Make submit always fail
        monkeypatch.setattr(forwarder, "submit", lambda fe: False)

        spooled = []
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or True)

        event = {"description": "needs retry"}
        forwarder.forward(event)

        # Contract: non-heartbeat failure triggers spool
        assert len(spooled) == 1
        assert spooled[0]["description"] == "needs retry"

    def test_own_forwarder_heartbeat_failure_no_spool(self, setup, monkeypatch):
        """
        AI-AGENT TEMPLATE: Heartbeat failure path.
        When submit() fails for a heartbeat event, the event should NOT
        be spooled (heartbeats are not retried).
        """
        forwarder = _new_forwarder(
            "example",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        monkeypatch.setattr(forwarder, "submit", lambda fe: False)

        spooled = []
        monkeypatch.setattr(forwarder, "spool", lambda raw_event: spooled.append(raw_event) or True)

        # Mock format_event to return a heartbeat event
        mock_formatted = _formatted_event({"description": "heartbeat"})
        mock_formatted.is_heartbeat = True
        monkeypatch.setattr(forwarder, "format_event", lambda raw: mock_formatted)

        forwarder.forward({"description": "heartbeat"})

        # Contract: heartbeat failure does NOT trigger spool
        assert len(spooled) == 0


class TestOwnFullTargetSmoke:
    def test_formatter_forwarder_pair(self, setup, monkeypatch):
        """
        AI-AGENT TEMPLATE: Combined formatter + forwarder pair smoke.
        Demonstrates the classic "ticket system integration" story:
        1. Format the event (set payload + summary)
        2. Forward the formatted event
        3. Verify the forwarder received the correct payload

        This is the pattern users follow when building a new integration
        for a ticket system (Jira, ServiceNow, etc.).
        """
        from notificationforwarder.vong.formatter import VongFormatter

        # Step 1: Format the event
        formatter = VongFormatter()
        event = _formatted_event({
            "HOSTNAME": "myhost",
            "SERVICEDESC": "myservice",
            "SERVICESTATE": "CRITICAL",
            "SERVICEOUTPUT": "disk full",
        })

        formatter.format_event(event)

        # Contract: formatter set payload and summary
        assert isinstance(event.payload, dict)
        assert isinstance(event.summary, str)
        assert "host_name" in event.payload
        assert event.payload["host_name"] == "myhost"

        # Step 2: Forward the formatted event
        forwarder = _new_forwarder(
            "vong",
            forwarder_name="webhook",
            forwarder_opts={"url": "http://example.invalid/api"},
        )

        captured = []
        original_submit = forwarder.submit

        def capture_submit(formatted_event):
            captured.append(formatted_event)
            return True

        monkeypatch.setattr(forwarder, "submit", capture_submit)

        raw_event = {
            "HOSTNAME": "myhost",
            "SERVICEDESC": "myservice",
            "SERVICESTATE": "CRITICAL",
            "SERVICEOUTPUT": "disk full",
        }

        forwarder.forward(raw_event)

        # Contract: forwarder received the formatted event
        assert len(captured) == 1
        assert captured[0].payload["host_name"] == "myhost"
