import logging
import os
import shutil
import sys

import pytest

from notificationforwarder import baseclass
from notificationforwarder.component_loader import resolve_component
from notificationforwarder.runtime_config import RuntimeConfig


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
def runtime_setup():
    _setup()
    yield


def get_logfile(forwarder):
    logger_name = "notificationforwarder_" + forwarder.forwarder_name
    logger = logging.getLogger(logger_name)
    return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


def test_runtime_config_normalizes_forwarder_options(runtime_setup):
    os.environ["NOTIFICATIONFORWARDER_LOGFILE_BACKUPS"] = "7"
    os.environ["NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES"] = "11"

    config = RuntimeConfig.from_inputs(
        "example",
        "blue",
        "example",
        verbose=False,
        debug=True,
        forwarder_opts={"logfile_backups": "4", "max_spool_minutes": "9", "username": "i_bims"},
        logger_type="json",
    )

    assert config.forwarder_name == "example_blue"
    assert config.logger_name == "notificationforwarder_example_blue"
    assert config.backup_count == 4
    assert config.max_spool_minutes == 9
    assert config.forwarder_opts == {"username": "i_bims"}
    assert config.screen_log_level == logging.DEBUG
    assert config.text_log_level == logging.DEBUG

    runtime_paths = config.build_paths()
    assert runtime_paths.db_file.endswith("var/tmp/notificationforwarder_example_blue_notifications.db")
    assert runtime_paths.db_lock_file.endswith("tmp/notificationforwarderexample_blue_flush.lock")

    del os.environ["NOTIFICATIONFORWARDER_LOGFILE_BACKUPS"]
    del os.environ["NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES"]


def test_resolve_component_supports_derived_and_explicit_names():
    assert resolve_component("json", "Logger") == ("json", "JsonLogger", "derived-class")
    assert resolve_component("custom.module.LoggerClass", "Logger") == (
        "custom.module",
        "LoggerClass",
        "explicit-class",
    )


def test_new_uses_text_logger_fallback_for_unknown_logger(runtime_setup):
    forwarder = baseclass.new(
        "example",
        None,
        "example",
        True,
        True,
        {"username": "i_bims", "password": "i_bims_1_i_bims"},
        logger_type="does_not_exist",
    )

    assert baseclass.logger.__class__.__name__ == "TextLogger"
    log = open(get_logfile(forwarder)).read()
    assert "Could not load logger type, falling back to text" in log


def test_new_creates_forwarder_formatter_and_runtime_paths(runtime_setup):
    forwarder = baseclass.new(
        "split1",
        None,
        "split1",
        True,
        True,
        {"username": "i_bims", "password": "dem_is_geheim"},
    )
    formatter = forwarder.new_formatter()

    assert forwarder.__class__.__name__ == "Split1Forwarder"
    assert formatter.__class__.__name__ == "Split1Formatter"
    assert forwarder.__module_file__.endswith("pythonpath/lib/python/notificationforwarder/split1/forwarder.py")
    assert formatter.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split1/formatter.py")
    assert forwarder.db_file.endswith("var/tmp/notificationforwarder_split1_notifications.db")
    assert forwarder.db_lock_file.endswith("tmp/notificationforwardersplit1_flush.lock")


def test_forward_runs_current_orchestration_flow(runtime_setup):
    forwarder = baseclass.new(
        "example",
        None,
        "example",
        True,
        True,
        {"username": "i_bims", "password": "i_bims_1_i_bims"},
    )

    event = {"description": "runtime flow test"}
    forwarder.forward(event)

    log = open(get_logfile(forwarder)).read()
    assert "INFO - i_bims submits" in log
    assert "INFO - forwarded sum: runtime flow test" in log
    assert event["omd_originating_host"]
    assert event["omd_originating_fqdn"]
    assert event["omd_originating_timestamp"].isdigit()
