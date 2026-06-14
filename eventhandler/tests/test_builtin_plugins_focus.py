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
    sys.path.append(os.environ["OMD_ROOT"] + "/../../notificationforwarder/src")
    sys.path.append(os.environ["OMD_ROOT"] + "/../src")

from eventhandler import baseclass
from eventhandler.baseclass import DecidedEvent
import eventhandler.text.logger as text_logger_module
import notificationforwarder.baseclass as notification_baseclass
from eventhandler.bash.runner import BashRunner
from eventhandler.ssh.runner import SshRunner
from eventhandler.nsc_web.runner import NscWebRunner
from eventhandler.default.decider import DefaultDecider
from eventhandler.omd_site_self_heal.decider import OmdSiteSelfHealDecider


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


def _new_runner(runner_name, decider_name="example", runner_opts=None, logger_type="text"):
    return baseclass.new(
        runner_name,
        None,
        decider_name,
        True,
        True,
        runner_opts or {},
        logger_type=logger_type,
    )


def _decided_event(eventopts):
    return DecidedEvent(dict(eventopts))


def _logfile(runner):
    logger_name = "eventhandler_" + runner.runner_name
    logger = logging.getLogger(logger_name)
    return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


def test_builtin_deciders_handle_state_transitions(setup):
    cases = [
        (
            "default",
            {
                "HOSTNAME": "h1",
                "SERVICEDESC": "svc",
                "HOSTDOWNTIME": False,
                "SERVICEDOWNTIME": False,
                "SERVICESTATE": "OK",
                "SERVICEATTEMPT": 1,
            },
            lambda event: event.is_discarded and event.summary == "svc / h1 has recovered",
        ),
        (
            "omd_site_self_heal",
            {
                "HOSTNAME": "h2",
                "SERVICEDESC": "svc",
                "site_name": "site-1",
                "HOSTDOWNTIME": False,
                "SERVICEDOWNTIME": False,
                "SERVICESTATE": "CRITICAL",
                "SERVICEATTEMPT": 1,
            },
            lambda event: event.summary == "restarting svc / h2" and event.payload["command"] == "local/lib/nagios/plugins/check_omd --heal",
        ),
    ]

    for decider_name, eventopts, check in cases:
        runner = _new_runner("example", decider_name)
        decider = runner.new_decider()
        event = _decided_event(eventopts)
        decider.decide_and_prepare(event)
        assert check(event)


def test_builtin_decider_modules_directly(setup):
    default = DefaultDecider()
    heal = OmdSiteSelfHealDecider()

    event1 = _decided_event({"HOSTNAME": "h1", "SERVICEDESC": "svc", "HOSTDOWNTIME": False, "SERVICEDOWNTIME": False, "SERVICESTATE": "OK", "SERVICEATTEMPT": 1})
    default.decide_and_prepare(event1)
    assert event1.is_discarded is True

    event2 = _decided_event({"HOSTNAME": "h2", "SERVICEDESC": "svc", "site_name": "site", "HOSTDOWNTIME": False, "SERVICEDOWNTIME": False, "SERVICESTATE": "CRITICAL", "SERVICEATTEMPT": 1})
    heal.decide_and_prepare(event2)
    assert event2.payload["user"] == "site"


def test_builtin_runners_render_expected_commands(setup):
    bash_runner = BashRunner({"command": "echo hello"})
    nsc_runner = NscWebRunner({"hostname": "nsc", "port": 9443, "password": "secret", "command": "check_uptime", "arguments": "-w 10"})

    assert bash_runner.run(_decided_event({"payload": {}})) == "bash -c 'echo hello'"
    assert "check_nsc_web -k -u https://nsc:9443 -p 'secret' -t 180 check_uptime '-w 10'" in nsc_runner.run(_decided_event({"payload": {}}))


def test_ssh_runner_instantiates_with_identity_file(setup):
    runner = SshRunner({"username": "root", "hostname": "remote", "port": 2222, "identity_file": "~/.ssh/id_rsa", "command": "uptime"})
    assert runner.hostname == "remote"
    assert runner.identity_file is not None
    assert "~" not in runner.identity_file


def test_handle_forwards_execution_results_and_survives_forwarder_errors(setup, monkeypatch):
    runner = _new_runner("example", "example", {"path": "/tmp"})
    monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "summary")))
    monkeypatch.setattr(runner, "run", lambda event: True)

    forwarded = []

    class BrokenForwarder:
        def forward(self, event):
            forwarded.append(event)
            raise RuntimeError("downstream failed")

    runner.forwarder = BrokenForwarder()
    assert runner.handle({"summary": "ignored", "content": "payload"}) is True
    assert forwarded and forwarded[0]["NOTIFICATIONTYPE"] == "EVENTHANDLER"


def test_concurrent_handle_attempt_is_suppressed(setup):
    runner = _new_runner("example", "example", {"path": "/tmp"})
    assert runner._handle_lock.acquire(blocking=False)
    try:
        assert runner.handle({"summary": "safe", "content": "payload"}) is None
    finally:
        runner._handle_lock.release()


def test_notification_forwarder_handoff_failure_is_logged(setup, monkeypatch):
    runner = _new_runner("example", "example", {"path": "/tmp"})
    monkeypatch.setattr(runner, "new_decider", lambda: SimpleNamespace(decide_and_prepare=lambda event: setattr(event, "payload", {"content": "hello"}) or setattr(event, "summary", "summary")))
    monkeypatch.setattr(runner, "run", lambda event: True)

    class BrokenForwarder:
        def forward(self, event):
            raise RuntimeError("handoff failed")

    runner.forwarder = BrokenForwarder()
    runner.handle({"summary": "safe", "content": "payload"})


def test_text_logger_fallback_is_used_when_logger_type_is_invalid(setup):
    runner = _new_runner("example", "example", {}, logger_type="missing_logger")
    assert runner is not None
    with open(_logfile(runner)) as fh:
        contents = fh.read()
    assert "falling back to text" in contents


def test_eventhandler_logger_output_is_structured(setup):
    runner = _new_runner("example", "example", {"path": "/tmp"})
    log_file = _logfile(runner)

    event = _decided_event({"HOSTNAME": "h", "SERVICEDESC": "svc"})
    event.summary = "summary"
    runner.no_more_logging()
    runner.run_result(event, True)

    with open(log_file) as fh:
        contents = fh.read()
    assert "Logger initialized" in contents


def test_builtin_logger_modules_fallback_and_text_output(setup):
    runner = _new_runner("example", "example", {}, logger_type="missing_logger")
    assert runner is not None
    with open(_logfile(runner)) as fh:
        contents = fh.read()
    assert "falling back to text" in contents
