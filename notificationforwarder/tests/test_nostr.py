import logging
import os
import shutil
import sys

import pytest

from notificationforwarder import baseclass
from notificationforwarder.nostr import formatter as nostr_formatter_module
from notificationforwarder.nostr import forwarder as nostr_forwarder_module


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
    return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


def test_nostr_formatter_builds_readable_note_and_default_tags(setup):
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

    assert event.payload["content"] == "Host: srv01\nService: http\nState: CRITICAL\nOutput: down"
    assert event.payload["tags"] == [
        ["t", "monitoring"],
        ["host", "srv01"],
        ["service", "http"],
        ["state", "CRITICAL"],
    ]
    assert event.summary == "srv01/http: CRITICAL"


def test_nostr_forwarder_publishes_to_relays_without_logging_secret(setup, monkeypatch):
    calls = {}

    class FakePrivateKey:
        @classmethod
        def from_nsec(cls, value):
            calls["nsec"] = value
            return cls()

        def hex(self):
            return "secret-hex"

    class FakeEvent:
        def __init__(self, content, tags=None):
            self.content = content
            self.tags = tags or []
            self.signed_by = None

        def sign(self, private_key_hex):
            self.signed_by = private_key_hex

    class FakeRelayManager:
        def __init__(self, timeout=6):
            calls["timeout"] = timeout
            self.relays = []
            self.published = []

        def add_relay(self, relay_url):
            self.relays.append(relay_url)

        def publish_event(self, event):
            self.published.append(event)

        def run_sync(self):
            calls["run_sync"] = True

        def close_all_relay_connections(self):
            calls["closed"] = True

    monkeypatch.setattr(nostr_forwarder_module, "PrivateKey", FakePrivateKey)
    monkeypatch.setattr(nostr_forwarder_module, "Event", FakeEvent)
    monkeypatch.setattr(nostr_forwarder_module, "RelayManager", FakeRelayManager)

    forwarder = baseclass.new(
        "nostr",
        None,
        "nostr",
        True,
        True,
        {
            "relays": "wss://relay.damus.io,wss://nostr-pub.wellorder.net",
            "nsec": "nsec1secret",
        },
    )

    event = baseclass.FormattedEvent({"HOSTNAME": "srv01", "SERVICESTATE": "OK"})
    event.payload = {
        "kind": 1,
        "content": "Host: srv01\nService: -\nState: OK\nOutput: -",
        "tags": [["t", "monitoring"], ["host", "srv01"], ["state", "OK"]],
    }
    event.summary = "srv01/-: OK"

    assert forwarder.submit(event) is True
    log = open(get_logfile(forwarder)).read()
    assert "nsec1secret" not in log
    assert "published Nostr note: srv01/-: OK" in log
    assert calls["nsec"] == "nsec1secret"
    assert calls["timeout"] == 6
    assert calls["run_sync"] is True
    assert calls["closed"] is True


def test_nostr_forwarder_reports_relay_failure(setup, monkeypatch):
    class FakePrivateKey:
        @classmethod
        def from_nsec(cls, value):
            return cls()

        def hex(self):
            return "secret-hex"

    class FakeEvent:
        def __init__(self, content, tags=None):
            self.content = content
            self.tags = tags or []

        def sign(self, private_key_hex):
            return None

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

    monkeypatch.setattr(nostr_forwarder_module, "PrivateKey", FakePrivateKey)
    monkeypatch.setattr(nostr_forwarder_module, "Event", FakeEvent)
    monkeypatch.setattr(nostr_forwarder_module, "RelayManager", BrokenRelayManager)

    forwarder = baseclass.new("nostr", None, "nostr", True, True, {"relays": "wss://relay.damus.io", "nsec": "nsec1secret"})
    event = baseclass.FormattedEvent({"HOSTNAME": "srv01"})
    event.payload = {"kind": 1, "content": "Host: srv01\nService: -\nState: -\nOutput: -", "tags": [["t", "monitoring"], ["host", "srv01"]]}
    event.summary = "srv01/-: -"

    assert forwarder.submit(event) is False
    log = open(get_logfile(forwarder)).read()
    assert "relay down" in log
    assert "nsec1secret" not in log
