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


def test_discard_do_not_discard(setup):
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    split3 = notificationforwarder.baseclass.new("split3", None, "discard", True, True,  forwarderopts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    cmd = "OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder split3 --forwarderopt username=i_bims --forwarderopt password=dem_is_geheim --formatter discard --eventopt description='halo i bims 1 alarm vong naemon her' --eventopt signature={} --eventopt was_i_machn_tu=nix".format(omd_root, pythonpath, cmd, signature)
    subprocess.call(cmd, shell=True)
    log = open(get_logfile(split3)).read()
    assert "forwarder" in log # written by split3 forwarder
    assert "forwarded" in log # written by the baseclass
    assert signature in log


def test_discard_discard_silently(setup):
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    split3 = notificationforwarder.baseclass.new("split3", None, "discard", True, True,  forwarderopts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    cmd = "OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder split3 --forwarderopt username=i_bims --forwarderopt password=dem_is_geheim --formatter discard --eventopt description='halo i bims 1 alarm vong naemon her' --eventopt signature={} --eventopt 'was_i_machn_tu=dem maul haltn'".format(omd_root, pythonpath, cmd, signature)
    subprocess.call(cmd, shell=True)
    log = open(get_logfile(split3)).read()
    assert "forwarder" not in log # written by split3 forwarder
    assert "forwarded" not in log # written by the baseclass
    assert "discard" not in log # written by the baseclass
    assert signature not in log


def test_discard_discard_with_own_comment(setup):
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    split3 = notificationforwarder.baseclass.new("split3", None, "discard", True, True,  forwarderopts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    cmd = "OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder split3 --forwarderopt username=i_bims --forwarderopt password=dem_is_geheim --formatter discard --eventopt description='halo i bims 1 alarm vong naemon her' --eventopt signature={} --eventopt 'was_i_machn_tu=dem semf dazugebn'".format(omd_root, pythonpath, cmd, signature)
    subprocess.call(cmd, shell=True)
    log = open(get_logfile(split3)).read()
    assert "forwarder" not in log # written by split3 forwarder
    assert "forwarded" not in log # written by the baseclass
    assert "discard" in log # written by the baseclass
    assert "dem semf" in log # written by the formatter
    assert signature not in log


def test_discard_discard_with_default_comment(setup):
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    split3 = notificationforwarder.baseclass.new("split3", None, "discard", True, True,  forwarderopts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    cmd = "OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder split3 --forwarderopt username=i_bims --forwarderopt password=dem_is_geheim --formatter discard --eventopt description='halo i bims 1 alarm vong naemon her' --eventopt signature={} --eventopt 'was_i_machn_tu=dem automatischn semf dazugebn'".format(omd_root, pythonpath, cmd, signature)
    subprocess.call(cmd, shell=True)
    log = open(get_logfile(split3)).read()
    assert "forwarder" not in log # written by split3 forwarder
    assert "forwarded" not in log # written by the baseclass
    assert "discard" in log # written by the baseclass
    assert "dem semf" not in log # written by the formatter
    assert signature in log

