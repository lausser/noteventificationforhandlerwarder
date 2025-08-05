import pytest
import inspect
import sys
import os
import re
import shutil
import hashlib, secrets
import logging
import subprocess
import hashlib, secrets
os.environ['PYTHONDONTWRITEBYTECODE'] = "true"


omd_root = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = omd_root
if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/lib/python")
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
    # forwarder*     formatter*
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    split1 = notificationforwarder.baseclass.new("split1", None, "split4", True, True,  forwarderopts)
    assert split1.__class__.__name__ == "Split1Forwarder"
    assert split1.__module_file__.endswith("pythonpath/lib/python/notificationforwarder/split1/forwarder.py")
    assert split1.password == "dem_is_geheim"
    assert split1.queued_events == []
    fsplit1 = split1.new_formatter()
    assert fsplit1.__class__.__name__ == "Split4Formatter"
    assert fsplit1.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split4/formatter.py")
    split1.forward(eventopts)
    log = open(get_logfile(split1)).read()
    assert re.search(r'forwarder '+split1.__module_file__, log)
    assert re.search(r'formatter '+fsplit1.__module_file__, log)


def test_split3_forwarder_split4_formatter(setup):
    # lib            local/lib
    # forwarder      forwarder*
    #                formatter*
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    split3 = notificationforwarder.baseclass.new("split3", None, "split4", True, True,  forwarderopts)
    assert split3.__class__.__name__ == "Split3Forwarder"
    assert split3.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split3/forwarder.py")
    assert split3.password == "dem_is_geheim"
    assert split3.queued_events == []
    fsplit3 = split3.new_formatter()
    assert fsplit3.__class__.__name__ == "Split4Formatter"
    assert fsplit3.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/split4/formatter.py")
    split3.forward(eventopts)
    log = open(get_logfile(split3)).read()
    assert "split4_" in log
    assert re.search(r'forwarder '+split3.__module_file__, log)
    assert re.search(r'formatter '+fsplit3.__module_file__, log)

def test_split3_forwarder_split4_formatter_bin_old(setup):
    # this is used to find out the logfile
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    split3 = notificationforwarder.baseclass.new("split3", None, "split4", True, True,  forwarderopts)
    # split4 formatter writes "split4_<optional signature>_split4" in the summary
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    print("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder split3 --forwarderopt username=i_bims --forwarderopt password=dem_is_geheim --formatter split4 --eventopt description='halo i bims 1 alarm vong naemon her' --eventopt signature={}".format(omd_root, pythonpath, cmd, signature))
    subprocess.call("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder split3 --forwarderopt username=i_bims --forwarderopt password=dem_is_geheim --formatter split4 --eventopt description='halo i bims 1 alarm vong naemon her' --eventopt signature={}".format(omd_root, pythonpath, cmd, signature), shell=True)
    log = open(get_logfile(split3)).read()
    assert "split4_"+signature+"_split4" in log

def test_split3_forwarder_split4_formatter_bin(setup):
    # this is used to find out the logfile
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    split3 = notificationforwarder.baseclass.new("split3", None, "split4", True, True,  forwarderopts)
    # split4 formatter writes "split4_<optional signature>_split4" in the summary
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    print("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder split3 --forwarderopt username=i_bims --forwarderopt password=dem_is_geheim --formatter split4 --eventopt description='halo i bims 1 alarm vong naemon her' --eventopt signature={}".format(omd_root, pythonpath, cmd, signature))
    subprocess.call("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder split3 --forwarderopt  username=i_bims --forwarderopt password=dem_is_geheim --formatter split4 --eventopt description='halo i bims 1 alarm vong naemon her' --eventopt signature={}".format(omd_root, pythonpath, cmd, signature), shell=True)
    log = open(get_logfile(split3)).read()
    assert "split4_"+signature+"_split4" in log


