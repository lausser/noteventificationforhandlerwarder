import pytest
import inspect
import sys
import os
import re
import shutil
import hashlib, secrets
import logging

omd_root = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = omd_root
if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/lib/python")
    print("PYTHONPATH="+":".join(sys.path))
import notificationforwarder.baseclass


def _setup():
    omd_root = os.path.dirname(__file__)
    os.environ["OMD_ROOT"] = omd_root
    shutil.rmtree(omd_root+"/var", ignore_errors=True)
    os.makedirs(omd_root+"/var/log", 0o755)
    shutil.rmtree(omd_root+"/var", ignore_errors=True)
    os.makedirs(omd_root+"/var/tmp", 0o755)
    shutil.rmtree(omd_root+"/tmp", ignore_errors=True)
    os.makedirs(omd_root+"/tmp", 0o755)
    if os.path.exists("/tmp/notificationforwarder_example.txt"):
        os.remove("/tmp/notificationforwarder_example.txt")

@pytest.fixture
def setup():
    _setup()
    yield

def get_logfile(forwarder):
    logger_name = "notificationforwarder_"+forwarder.name
    logger = logging.getLogger(logger_name)
    return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


def test_split4_inheritance(setup):
    # local/lib      local/lib
    # forwarder      formatter
    # split1         split3    <- inherits from
    # 
    print("PYTHONPATH="+":".join(sys.path))
    reveiveropts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    split4 = notificationforwarder.baseclass.new("split4", None, "split2", True, True,  reveiveropts)
    assert split4.__class__.__name__ == "Split4Forwarder"
    assert split4.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split4/forwarder.py")
    assert split4.password == "dem_is_geheim"
    assert split4.queued_events == []
    fsplit4 = split4.new_formatter()
    assert fsplit4.__class__.__name__ == "Split4Formatter"
    assert fsplit4.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split4/formatter.py")
    split4.forward(eventopts)
    log = open(get_logfile(split4)).read()
    print(log)
    assert re.search(r'forwarder '+split4.__module_file__, log)
    assert re.search(r'formatter '+fsplit4.__module_file__, log)


