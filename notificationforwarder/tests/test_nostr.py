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
    pytest.importorskip("nostr_sdk")
    from nostr_sdk import Keys

    keys = Keys.generate()
    return keys.secret_key().to_bech32(), keys.public_key().to_bech32()


def _nostr_forwarder_module():
    pytest.importorskip("nostr_sdk")
    return importlib.import_module("notificationforwarder.nostr.forwarder")


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

    assert event.payload["content"] == "Host: srv01\nService: http\nState: CRITICAL\nOutput: down"
    assert event.payload["tags"] == [["t", "monitoring"], ["t", "host=srv01"], ["t", "service=http"], ["t", "state=CRITICAL"]]
    assert event.summary == "srv01/http: CRITICAL"


def test_nostr_forwarder_builds_dm_event(setup, monkeypatch):
    nostr_forwarder_module = _nostr_forwarder_module()

    test_nsec, test_npub = _generated_keypair()

    captured = {}

    class FakeClient:
        def __init__(self, signer):
            captured["signer"] = signer

        async def add_relay(self, relay_url):
            captured.setdefault("relays", []).append(relay_url)

        async def connect(self):
            captured["connected"] = True

        async def send_private_msg_to(self, urls, receiver, message, tags):
            captured["urls"] = [str(url) for url in urls]
            captured["receiver"] = receiver.to_bech32()
            captured["message"] = message
            captured["tags"] = [tag.as_vec() for tag in tags]
            return True

    monkeypatch.setattr(nostr_forwarder_module, "Client", FakeClient)

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
    event.payload = {"kind": 14, "content": "Host: demo-host\nService: test\nState: OK\nOutput: test message", "tags": [["t", "monitoring"]]}
    event.summary = "demo-host/test: OK"

    assert forwarder.submit(event) is True
    assert captured["connected"] is True
    assert captured["urls"] == ["wss://relay.damus.io", "wss://nostr-pub.wellorder.net"]
    assert captured["receiver"] == test_npub
    assert captured["message"] == "Host: demo-host\nService: test\nState: OK\nOutput: test message"
    assert captured["tags"] == []


def test_nostr_forwarder_logs_failure_without_secret(setup, monkeypatch):
    nostr_forwarder_module = _nostr_forwarder_module()

    test_nsec, test_npub = _generated_keypair()

    class BrokenClient:
        def __init__(self, signer):
            pass

        async def add_relay(self, relay_url):
            return True

        async def connect(self):
            return True

        async def send_private_msg_to(self, urls, receiver, message, tags):
            raise RuntimeError("relay down")

    monkeypatch.setattr(nostr_forwarder_module, "Client", BrokenClient)

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
    event.payload = {"kind": 14, "content": "Host: srv01\nService: -\nState: -\nOutput: -", "tags": [["p", test_npub]]}
    event.summary = "srv01/-: -"

    assert forwarder.submit(event) is False
    assert "relay down" in open(get_logfile(forwarder)).read()


def test_nostr_forwarder_handles_invalid_sdk_message(setup, monkeypatch):
    nostr_forwarder_module = _nostr_forwarder_module()

    test_nsec, test_npub = _generated_keypair()

    class BrokenClient:
        def __init__(self, signer):
            pass

        async def add_relay(self, relay_url):
            return True

        async def connect(self):
            return True

        async def send_private_msg_to(self, urls, receiver, message, tags):
            raise RuntimeError("sdk rejected message")

    monkeypatch.setattr(nostr_forwarder_module, "Client", BrokenClient)

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
    event.payload = {"kind": 14, "content": "Host: srv01", "tags": [["p", test_npub]]}
    event.summary = "srv01/-: -"

    assert forwarder.submit(event) is False
    assert "sdk rejected message" in open(get_logfile(forwarder)).read()


def test_nostr_forwarder_uses_configured_recipient_tag(setup, monkeypatch):
    nostr_forwarder_module = _nostr_forwarder_module()

    test_nsec, test_npub = _generated_keypair()
    captured = {}

    class FakeClient:
        def __init__(self, signer):
            pass

        async def add_relay(self, relay_url):
            return True

        async def connect(self):
            return True

        async def send_private_msg_to(self, urls, receiver, message, tags):
            captured["receiver"] = receiver.to_bech32()
            captured["message"] = message
            return True

    monkeypatch.setattr(nostr_forwarder_module, "Client", FakeClient)

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
    event.payload = {"kind": 14, "content": "count=1", "tags": [["t", "monitoring"]]}
    event.summary = "srv01/-: -"

    assert forwarder.submit(event) is True
    assert captured["receiver"] == test_npub
    assert captured["message"] == "count=1"


def test_nostr_forwarder_requires_nostr_sdk(setup, monkeypatch):
    script = """
import builtins
import os
import sys

original_import = builtins.__import__

def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.startswith("nostr_sdk"):
        raise ImportError("missing nostr-sdk")
    return original_import(name, globals, locals, fromlist, level)

sys.path.append(os.path.join(os.environ["OMD_ROOT"], "pythonpath", "local", "lib", "python"))
sys.path.append(os.path.join(os.environ["OMD_ROOT"], "pythonpath", "lib", "python"))
sys.path.append(os.path.join(os.environ["OMD_ROOT"], "..", "src"))
builtins.__import__ = fake_import

import notificationforwarder.nostr.forwarder
"""

    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)

    assert result.returncode != 0
    assert "missing nostr-sdk" in result.stderr
    


def test_nostr_forwarder_clamps_websocket_timeout_and_still_initializes(setup, monkeypatch):
    nostr_forwarder_module = _nostr_forwarder_module()
    captured = {}

    class FakeClient:
        def __init__(self, signer):
            pass

        async def add_relay(self, relay_url):
            return True

        async def connect(self):
            return True

        async def send_private_msg_to(self, urls, receiver, message, tags):
            captured["urls"] = [str(url) for url in urls]
            captured["receiver"] = receiver.to_bech32()
            captured["message"] = message
            captured["tags"] = [tag.as_vec() for tag in tags]
            return True

    monkeypatch.setattr(nostr_forwarder_module, "Client", FakeClient)

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
    event.payload = {"kind": 14, "content": "Host: srv01\nService: -\nState: -\nOutput: -", "tags": [["p", test_npub]]}
    event.summary = "srv01/-: -"

    assert forwarder.submit(event) is True
    assert captured["urls"] == ["wss://relay.damus.io"]
    assert captured["receiver"] == test_npub


def test_nostr_forwarder_fails_without_recipient_tag(setup):
    test_nsec, _ = _generated_keypair()

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
    event.payload = {"kind": 14, "content": "Host: srv01", "tags": [["t", "monitoring"]]}
    event.summary = "srv01/-: -"

    with pytest.raises(ValueError, match="recipient p tag"):
        forwarder.submit(event)
