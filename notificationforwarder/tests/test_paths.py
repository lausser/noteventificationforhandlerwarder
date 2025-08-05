import pytest
import inspect
import sys
import os
import re
import shutil
import hashlib, secrets
import logging
os.environ['PYTHONDONTWRITEBYTECODE'] = "true"


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


def test_split1_forwarder(setup):
    # lib            local/lib
    # forwarder      formatter
    print(sys.path)
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    split1 = notificationforwarder.baseclass.new("split1", None, "split1", True, True,  forwarderopts)
    assert split1.__class__.__name__ == "Split1Forwarder"
    assert split1.__module_file__.endswith("pythonpath/lib/python/notificationforwarder/split1/forwarder.py")
    assert split1.password == "dem_is_geheim"
    assert split1.queued_events == []
    fsplit1 = split1.new_formatter()
    assert fsplit1.__class__.__name__ == "Split1Formatter"
    assert fsplit1.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split1/formatter.py")
    split1.forward(eventopts)
    log = open(get_logfile(split1)).read()
    print(log)
    assert re.search(r'forwarder '+split1.__module_file__, log)
    assert re.search(r'formatter '+fsplit1.__module_file__, log)


def test_split2_forwarder(setup):
    # lib            local/lib
    # forwarder      forwarder
    # formatter
    print(sys.path)
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    split2 = notificationforwarder.baseclass.new("split2", None, "split2", True, True,  forwarderopts)
    assert split2.__class__.__name__ == "Split2Forwarder"
    assert split2.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split2/forwarder.py")
    assert split2.password == "dem_is_geheim"
    assert split2.queued_events == []
    fsplit2 = split2.new_formatter()
    assert fsplit2.__class__.__name__ == "Split2Formatter"
    assert fsplit2.__module_file__.endswith("pythonpath/lib/python/notificationforwarder/split2/formatter.py")
    split2.forward(eventopts)
    log = open(get_logfile(split2)).read()
    print(log)
    assert re.search(r'forwarder '+split2.__module_file__, log)
    assert re.search(r'formatter '+fsplit2.__module_file__, log)


def test_split3_forwarder(setup):
    # lib            local/lib
    # forwarder      forwarder
    # formatter      formatter
    print(sys.path)
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    split3 = notificationforwarder.baseclass.new("split3", None, "split3", True, True,  forwarderopts)
    assert split3.__class__.__name__ == "Split3Forwarder"
    assert split3.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split3/forwarder.py")
    assert split3.password == "dem_is_geheim"
    assert split3.queued_events == []
    fsplit3 = split3.new_formatter()
    assert fsplit3.__class__.__name__ == "Split3Formatter"
    assert fsplit3.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split3/formatter.py")
    split3.forward(eventopts)
    log = open(get_logfile(split3)).read()
    print(log)
    assert re.search(r'forwarder '+split3.__module_file__, log)
    assert re.search(r'formatter '+fsplit3.__module_file__, log)


