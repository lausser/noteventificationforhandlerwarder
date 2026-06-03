import logging
import os
import shutil
import sys

import pytest

from notificationforwarder import baseclass
from notificationforwarder.nostr import formatter as nostr_formatter_module
from notificationforwarder.nostr import forwarder as nostr_forwarder_module


TEST_NSEC = "TEST_NSEC_PLACEHOLDER"
TEST_NPUB = "TEST_NPUB_PLACEHOLDER"


os.environ["PYTHONDONTWRITEBYTECODE"] = "true"
OMD_ROOT = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = OMD_ROOT

if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/../src")


def _setup():
    omd_root = os.path.dirname(__file__)
    os.environ["OMD_ROOT"] = omd_root
    shutil.rmtree(omd_root + "/var", ignore_errors=True)
    os.makedirs(omd_root + "/var/log", 0o755)
    shutil.rmtree(omd_root + "/var", ignore_errors=True)
    os.makedirs(omd_root + "/var/tmp", 0o755)
    shutil.rmtree(omd_root + "/tmp", ignore_errors=True)
    os.makedirs(omd_root + "/tmp", 0o755)


@pytest.fixture
def setup():
    _setup()
    yield


def get_logfile(forwarder):
    logger_name = "notificationforwarder_" + forwarder.name
    logger = logging.getLogger(logger_name)
    for handler in logger.handlers:
        flush = getattr(handler, "flush", None)
        if callable(flush):
            flush()
    return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


def test_nostr_formatter_builds_readable_message(setup):
    formatter = nostr_formatter_module.NostrFormatter()
    event = baseclass.FormattedEvent(
        {
            "HOSTNAME": "srv01",
            "SERVICEDESC": "http",
            "SERVICESTATE": "CRITICAL",
            "SERVICEOUTPUT": "down",
        }
    )

    formatter.format_event(event)

    assert event.payload["kind"] == 4
    assert event.payload["content"] == "Host: srv01\nService: http\nState: CRITICAL\nOutput: down"
    assert event.payload["tags"] == [["t", "monitoring"], ["host", "srv01"], ["service", "http"], ["state", "CRITICAL"]]
    assert event.summary == "srv01/http: CRITICAL"


def test_nostr_forwarder_builds_dm_event(setup, monkeypatch):
    class FakeRelayManager:
        def __init__(self, timeout=6):
            self.timeout = timeout
            self.relays = []
            self.published = []

        def add_relay(self, relay_url):
            self.relays.append(relay_url)

        def publish_event(self, event):
            self.published.append(event)

        def run_sync(self):
            return True

        def close_all_relay_connections(self):
            return True

    monkeypatch.setattr(nostr_forwarder_module, "RelayManager", FakeRelayManager)

    forwarder = baseclass.new(
        "nostr",
        None,
        "nostr",
        True,
        True,
        {
            "relays": "wss://relay.damus.io,wss://nostr-pub.wellorder.net",
            "nsec": TEST_NSEC,
            "tags": f'[["p", "{TEST_NPUB}"]]',
        },
    )

    event = baseclass.FormattedEvent({"HOSTNAME": "demo-host", "SERVICEDESC": "test", "SERVICESTATE": "OK", "SERVICEOUTPUT": "test message"})
    event.payload = {"kind": 4, "content": "Host: demo-host\nService: test\nState: OK\nOutput: test message", "tags": [["t", "monitoring"]]}
    event.summary = "demo-host/test: OK"

    assert forwarder.submit(event) is True
    built = forwarder._build_event(event)
    assert [tag for tag in built.tags if tag[0] == "p"] == [["p", TEST_NPUB]]


def test_nostr_forwarder_logs_failure_without_secret(setup, monkeypatch):
    class BrokenRelayManager:
        def __init__(self, timeout=6):
            pass

        def add_relay(self, relay_url):
            pass

        def publish_event(self, event):
            raise RuntimeError("relay down")

        def run_sync(self):
            return None

        def close_all_relay_connections(self):
            return None

    monkeypatch.setattr(nostr_forwarder_module, "RelayManager", BrokenRelayManager)

    forwarder = baseclass.new(
        "nostr",
        None,
        "nostr",
        True,
        True,
        {
            "relays": "wss://relay.damus.io",
            "nsec": TEST_NSEC,
        },
    )
    event = baseclass.FormattedEvent({"HOSTNAME": "srv01"})
    event.payload = {"kind": 4, "content": "Host: srv01\nService: -\nState: -\nOutput: -", "tags": [["p", TEST_NPUB]]}
    event.summary = "srv01/-: -"

    assert forwarder.submit(event) is False
    assert "relay down" in open(get_logfile(forwarder)).read()
