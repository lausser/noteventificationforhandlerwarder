import logging
import os
import subprocess
import shutil
import sys
import importlib

import pytest

from notificationforwarder import baseclass


TEST_NSEC = "TEST_NSEC_PLACEHOLDER"
TEST_NPUB = "TEST_NPUB_PLACEHOLDER"


def _generated_keypair():
    pytest.importorskip("pynostr")
    from pynostr.key import PrivateKey

    private_key = PrivateKey()
    return private_key.nsec, private_key.public_key.npub


def _nostr_forwarder_module():
    pytest.importorskip("pynostr")
    return importlib.import_module("notificationforwarder.nostr.forwarder")


def _pynostr_relay_module():
    pytest.importorskip("pynostr")
    return importlib.import_module("pynostr.relay")


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
    formatter_module = importlib.import_module("notificationforwarder.nostr.formatter")
    formatter = formatter_module.NostrFormatter()
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
    nostr_forwarder_module = _nostr_forwarder_module()

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

    test_nsec, test_npub = _generated_keypair()

    forwarder = baseclass.new(
        "nostr",
        None,
        "nostr",
        True,
        True,
        {
            "relays": "wss://relay.damus.io,wss://nostr-pub.wellorder.net",
            "nsec": test_nsec,
            "tags": f'[["p", "{test_npub}"]]',
        },
    )

    event = baseclass.FormattedEvent({"HOSTNAME": "demo-host", "SERVICEDESC": "test", "SERVICESTATE": "OK", "SERVICEOUTPUT": "test message"})
    event.payload = {"kind": 4, "content": "Host: demo-host\nService: test\nState: OK\nOutput: test message", "tags": [["t", "monitoring"]]}
    event.summary = "demo-host/test: OK"

    assert forwarder.submit(event) is True
    built = forwarder._build_event(event)
    from pynostr.key import PublicKey

    assert [tag for tag in built.tags if tag[0] == "p"] == [["p", PublicKey.from_npub(test_npub).hex()]]


def test_nostr_forwarder_logs_failure_without_secret(setup, monkeypatch):
    nostr_forwarder_module = _nostr_forwarder_module()

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

    test_nsec, test_npub = _generated_keypair()

    forwarder = baseclass.new(
        "nostr",
        None,
        "nostr",
        True,
        True,
        {
            "relays": "wss://relay.damus.io",
            "nsec": test_nsec,
        },
    )
    event = baseclass.FormattedEvent({"HOSTNAME": "srv01"})
    event.payload = {"kind": 4, "content": "Host: srv01\nService: -\nState: -\nOutput: -", "tags": [["p", test_npub]]}
    event.summary = "srv01/-: -"

    assert forwarder.submit(event) is False
    assert "relay down" in open(get_logfile(forwarder)).read()


def test_nostr_forwarder_requires_pynostr(setup, monkeypatch):
    script = """
import builtins
import os
import sys

original_import = builtins.__import__

def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.startswith("pynostr"):
        raise ImportError("missing pynostr")
    return original_import(name, globals, locals, fromlist, level)

sys.path.append(os.path.join(os.environ["OMD_ROOT"], "pythonpath", "local", "lib", "python"))
sys.path.append(os.path.join(os.environ["OMD_ROOT"], "pythonpath", "lib", "python"))
sys.path.append(os.path.join(os.environ["OMD_ROOT"], "..", "src"))
builtins.__import__ = fake_import

import notificationforwarder.nostr.forwarder
"""

    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)

    assert result.returncode != 0
    assert "missing pynostr" in result.stderr
    


def test_nostr_forwarder_clamps_websocket_timeout_and_still_initializes(setup, monkeypatch):
    nostr_forwarder_module = _nostr_forwarder_module()
    pynostr_relay = _pynostr_relay_module()

    captured = {}

    def fake_websocket_connect(*args, **kwargs):
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(pynostr_relay, "websocket_connect", fake_websocket_connect)

    class FakeRelayManager:
        def __init__(self, timeout=6):
            self.timeout = timeout

        def add_relay(self, relay_url):
            self.relay_url = relay_url

        def publish_event(self, event):
            self.event = event

        def run_sync(self):
            pynostr_relay.websocket_connect("ws://example", ping_interval=60, ping_timeout=120)

        def close_all_relay_connections(self):
            return True

    monkeypatch.setattr(nostr_forwarder_module, "RelayManager", FakeRelayManager)

    test_nsec, test_npub = _generated_keypair()
    forwarder = baseclass.new(
        "nostr",
        None,
        "nostr",
        True,
        True,
        {
            "relays": "wss://relay.damus.io",
            "nsec": test_nsec,
            "tags": f'[["p", "{test_npub}"]]',
        },
    )

    event = baseclass.FormattedEvent({"HOSTNAME": "srv01"})
    event.payload = {"kind": 4, "content": "Host: srv01\nService: -\nState: -\nOutput: -", "tags": [["p", test_npub]]}
    event.summary = "srv01/-: -"

    assert forwarder.submit(event) is True
    assert captured["kwargs"]["ping_interval"] == 60
    assert captured["kwargs"]["ping_timeout"] == 60
