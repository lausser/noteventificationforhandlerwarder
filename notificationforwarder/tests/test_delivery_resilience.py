import logging
import os
import shutil
import sys
import time

import pytest

from notificationforwarder import baseclass
from notificationforwarder.baseclass import ForwarderTimeoutError, timeout


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
    if os.path.exists("/tmp/notificationforwarder_example.txt"):
        os.remove("/tmp/notificationforwarder_example.txt")
    if os.path.exists("/tmp/notificationforwarder_example_api.txt"):
        os.remove("/tmp/notificationforwarder_example_api.txt")


@pytest.fixture
def resilience_setup():
    _setup()
    yield


def get_logfile(forwarder):
    logger_name = "notificationforwarder_" + forwarder.forwarder_name
    logger = logging.getLogger(logger_name)
    return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


def new_example_forwarder(**forwarder_opts):
    opts = {"username": "i_bims", "password": "i_bims_1_i_bims"}
    opts.update(forwarder_opts)
    return baseclass.new("example", None, "example", True, True, opts)


def test_failed_delivery_is_spooled_and_logged(resilience_setup):
    forwarder = new_example_forwarder(fail="1")

    forwarder.forward({"description": "spool me"})

    assert forwarder.num_spooled_events() == 1
    log = open(get_logfile(forwarder)).read()
    assert "CRITICAL - sample api does not accept the payload" in log
    assert "WARNING - forward failed" in log
    assert "spooled <sum: spool me>" in log
    assert "WARNING - spooling queue length is 1" in log


def test_unrecoverable_failure_is_logged_when_spooling_fails(resilience_setup, monkeypatch):
    forwarder = new_example_forwarder(fail="1")

    monkeypatch.setattr(forwarder, "spool", lambda raw_event: False)

    forwarder.forward({"description": "cannot persist me"})

    log = open(get_logfile(forwarder)).read()
    assert "CRITICAL - sample api does not accept the payload" in log
    assert "CRITICAL - delivery failed and event could not be persisted <sum: cannot persist me>" in log


def test_flush_replays_spooled_events_on_recovery(resilience_setup):
    failing_forwarder = new_example_forwarder(fail="1")
    failing_forwarder.forward({"description": "first spooled", "signature": "sig-1"})
    failing_forwarder.forward({"description": "second spooled", "signature": "sig-2"})
    assert failing_forwarder.num_spooled_events() == 2

    recovering_forwarder = new_example_forwarder()
    recovering_forwarder.forward({"description": "trigger replay", "signature": "sig-3"})

    assert recovering_forwarder.num_spooled_events() == 0
    log = open(get_logfile(recovering_forwarder)).read()
    assert "INFO - there are 2 spooled events to be re-sent" in log
    assert "INFO - delete spooled event 1" in log
    assert "INFO - delete spooled event 2" in log
    assert "INFO - spool replay summary: attempted=2, recovered=2, stayed_in_spool=0, deleted_trash=0, dropped=0" in log

    signatures = [line.strip() for line in open(recovering_forwarder.signaturefile).readlines()]
    assert signatures == ["sig-1", "sig-2", "sig-3"]


def test_flush_drops_expired_spooled_events(resilience_setup):
    forwarder = new_example_forwarder(fail="1", max_spool_minutes="1")
    forwarder.forward({"description": "expire me", "signature": "sig-expired"})
    assert forwarder.num_spooled_events() == 1

    forwarder.dbcurs.execute(
        "UPDATE {table} SET timestamp = datetime('now', '-10 minutes')".format(table=forwarder.table_name)
    )
    forwarder.dbconn.commit()

    recovering_forwarder = new_example_forwarder(max_spool_minutes="1")
    recovering_forwarder.forward({"description": "flush after expiry", "signature": "sig-live"})

    assert recovering_forwarder.num_spooled_events() == 0
    log = open(get_logfile(recovering_forwarder)).read()
    assert "INFO - dropped 1 outdated events" in log
    assert "INFO - spool replay summary: attempted=0, recovered=0, stayed_in_spool=0, deleted_trash=0, dropped=1" in log
    signatures = [line.strip() for line in open(recovering_forwarder.signaturefile).readlines()]
    assert signatures == ["sig-live"]


def test_flush_logs_when_concurrent_lock_is_unavailable(resilience_setup, monkeypatch):
    forwarder = new_example_forwarder()

    monkeypatch.setattr(forwarder, "acquire_lock_with_retry", lambda lock_file, max_attempts=3, base_delay=0.1: False)

    forwarder.flush()

    log = open(get_logfile(forwarder)).read()
    assert "INFO - concurrent flush suppressed" in log
    assert "DEBUG - missed the flush lock" in log


def test_timeout_decorator_raises_forwarder_timeout():
    @timeout(0.01, error_message="submit ran into a timeout")
    def slow_call():
        time.sleep(0.05)
        return True

    with pytest.raises(ForwarderTimeoutError, match="submit ran into a timeout"):
        slow_call()


def test_timeout_decorator_preserves_underlying_exception():
    @timeout(0.5, error_message="submit ran into a timeout")
    def broken_call():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        broken_call()
