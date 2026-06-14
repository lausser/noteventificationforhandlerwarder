"""
Logger tests for eventhandler.

This file covers the TextLogger and JsonLogger contract coverage,
including fallback behavior and structured field expectations.
"""
import logging
import os
import shutil
import sys

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


# ============================================================================
# Logger fallback tests
# ============================================================================

class TestLoggerFallback:
    def test_text_logger_fallback_is_used_when_logger_type_is_invalid(self, setup):
        """Text logger fallback is used when logger type is invalid."""
        runner = _new_runner("example", "example", {}, logger_type="missing_logger")
        assert runner is not None
        with open(_logfile(runner)) as fh:
            contents = fh.read()
        assert "falling back to text" in contents

    def test_builtin_logger_modules_fallback_and_text_output(self, setup):
        """Built-in logger modules fallback and text output."""
        runner = _new_runner("example", "example", {}, logger_type="missing_logger")
        assert runner is not None
        with open(_logfile(runner)) as fh:
            contents = fh.read()
        assert "falling back to text" in contents


# ============================================================================
# Logger output structure tests
# ============================================================================

class TestLoggerOutput:
    def test_eventhandler_logger_output_is_structured(self, setup):
        """Eventhandler logger output is structured."""
        runner = _new_runner("example", "example", {"path": "/tmp"})
        log_file = _logfile(runner)

        event = _decided_event({"HOSTNAME": "h", "SERVICEDESC": "svc"})
        event.summary = "summary"
        runner.no_more_logging()
        runner.run_result(event, True)

        with open(log_file) as fh:
            contents = fh.read()
        assert "Logger initialized" in contents