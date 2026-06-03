import json
import logging
import os
import shutil
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
import notificationforwarder.webhook.forwarder as webhook_module
import notificationforwarder.telegram.forwarder as telegram_module
from notificationforwarder.naemonlog.reporter import NaemonlogReporter
from notificationforwarder.text.logger import TextLogger
from notificationforwarder.json.logger import JsonLogger


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


def test_builtin_formatters_render_expected_payloads(setup):
    cases = [
        (
            "email",
            {
                "HOSTNAME": "mailhost",
                "HOSTADDRESS": "127.0.0.1",
                "NOTIFICATIONTYPE": "PROBLEM",
                "SERVICEDESC": "smtp",
                "SERVICESTATE": "CRITICAL",
                "SERVICEOUTPUT": "smtp down",
            },
            lambda event: (
                event.summary == "mail"
                and set(event.payload) == {"html", "text", "subject"}
                and "mailhost" in event.payload["html"]
                and "smtp" in event.payload["text"]
            ),
        ),
        (
            "syslog",
            {
                "HOSTNAME": "syshost",
                "HOSTSTATE": "DOWN",
                "HOSTOUTPUT": "host down",
            },
            lambda event: event.summary == "host: syshost, state: DOWN"
            and event.payload == "host: syshost, state: DOWN, output: host down",
        ),
        (
            "rabbitmq",
            {
                "HOSTNAME": "queuehost",
                "NOTIFICATIONTYPE": "PROBLEM",
                "HOSTSTATE": "DOWN",
                "HOSTOUTPUT": "queue down",
            },
            lambda event: event.summary == str(event.payload[0])
            and event.payload[0]["host_name"] == "queuehost"
            and event.payload[0]["state"] == "DOWN",
        ),
        (
            "example",
            {
                "description": "hello world",
                "signature": "sig-1",
            },
            lambda event: event.summary == "sum: hello world"
            and event.payload["description"] == "hello world"
            and event.payload["signature"] == "sig-1"
            and "timestamp" in event.payload,
        ),
    ]

    for formatter_name, eventopts, check in cases:
        forwarder = _new_forwarder(formatter_name)
        formatter = forwarder.new_formatter()
        event = _formatted_event(eventopts)
        formatter.format_event(event)
        assert check(event)


def test_webhook_submit_one_supports_modes_and_overrides(setup, monkeypatch):
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


def test_webhook_forward_failure_spools_and_handles_spool_errors(setup, monkeypatch):
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


def test_telegram_forwarder_list_and_heartbeat_paths(setup, monkeypatch):
    forwarder = telegram_module.TelegramForwarder({"bot_token": "token", "chat_id": "chat"})
    event = _formatted_event({"description": "telegram"})
    event.payload = "hello"
    event.summary = "telegram summary"

    monkeypatch.setattr(forwarder, "submit_one", lambda one_event: one_event.payload == "hello")
    assert forwarder.submit([event]) is True

    heartbeat = _formatted_event({"description": "heartbeat"})
    heartbeat.payload = "hello"
    heartbeat.summary = "heartbeat summary"
    heartbeat.is_heartbeat = True
    monkeypatch.setattr(forwarder, "submit_one", lambda one_event: False)
    assert forwarder.submit(heartbeat) is True


def test_telegram_forwarder_submit_one_failure_returns_false(setup, monkeypatch):
    dummy_logger = SimpleNamespace(critical=lambda *args, **kwargs: None)
    monkeypatch.setattr(telegram_module, "logger", dummy_logger, raising=False)
    forwarder = telegram_module.TelegramForwarder({"bot_token": "token", "chat_id": "chat"})
    event = _formatted_event({"description": "telegram"})
    event.payload = "hello"
    event.summary = "telegram summary"

    assert forwarder.submit_one(event) is False


def test_naemonlog_reporter_writes_expected_host_and_service_lines(setup):
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


def test_builtin_logger_modules_format_text_and_json(setup):
    logger = logging.getLogger("notificationforwarder_test")
    text = TextLogger("notificationforwarder_test", logger)
    json_logger = JsonLogger("notificationforwarder_test", logger, version="1.0")

    event = _formatted_event({"HOSTNAME": "h", "SERVICEDESC": "svc", "SERVICESTATE": "CRITICAL"})
    event.summary = "summary"

    text.info("forwarded", {"formatted_event": event, "status": "success"})
    json_logger.info("forwarded", {"formatted_event": event, "status": "success"})
