import pytest
import sys
import os
import re
import time
import shutil
import hashlib, secrets
import eventhandler.baseclass
import logging
os.environ['PYTHONDONTWRITEBYTECODE'] = "true"


omd_root = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = omd_root
if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/lib/python")
import eventhandler.baseclass


def _setup():
    omd_root = os.path.dirname(__file__)
    os.environ["OMD_ROOT"] = omd_root
    shutil.rmtree(omd_root+"/var", ignore_errors=True)
    os.makedirs(omd_root+"/var/log", 0o755)
    os.makedirs(omd_root+"/var/tmp", 0o755)
    shutil.rmtree(omd_root+"/tmp", ignore_errors=True)
    os.makedirs(omd_root+"/tmp", 0o755)
    if os.path.exists(omd_root+"/var/log/eventhandler.debug"):
        os.remove(omd_root+"/var/log/eventhandler.debug")
    if os.path.exists("/tmp/eventhandler_example.txt"):
        os.remove("/tmp/eventhandler_example.txt")
    if os.path.exists("/tmp/echo"):
        os.remove("/tmp/echo")

@pytest.fixture
def setup():
    _setup()
    yield

def get_logfile(runner):
    logger_name = "eventhandler_"+runner.name
    logger = logging.getLogger(logger_name)
    return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


def test_example_runner(setup):
    reveiveropts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  reveiveropts)
    assert example.__class__.__name__ == "ExampleRunner"
    assert example.password == "dem_is_geheim"


def test_example_decider(setup):
    example = eventhandler.baseclass.new("example", None, "example", True, True,  {})
    dexample = example.new_decider()
    assert dexample.__class__.__name__ == "ExampleDecider"


def test_example_logging(setup):
    example = eventhandler.baseclass.new("example", None, "example", True, True,  {})
    logger_name = "eventhandler_"+example.name
    logger = logging.getLogger(logger_name)
    assert logger != None
    assert logger.name == "eventhandler_example"
    assert len([h for h in logger.handlers]) == 2
    logfile = [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]
    assert logfile.endswith("eventhandler_example.log")

    example = eventhandler.baseclass.new("example", "2", "example", True, True,  {})
    logger_name = "eventhandler_"+example.name+"_"+example.tag
    logger = logging.getLogger(logger_name)
    assert logger != None
    assert logger.name == "eventhandler_example_2"
    assert len(logger.handlers) == 2
    logfile = [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]
    assert logfile.endswith("eventhandler_example_2.log")
    

def test_example_decider_prepare_event(setup):
    sig = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    example = eventhandler.baseclass.new("example", None, "example", True, True,  {})
    dexample = example.new_decider()
    raw_event = {
        "content": "halo i bims 1 alarm vong naemon her",
        "summary": "samari"+sig,
        "timestamp": time.time(),
    }
    event = eventhandler.baseclass.DecidedEvent(raw_event)
    assert event.eventopts["content"] == "halo i bims 1 alarm vong naemon her"
    dexample.decide_and_prepare(event)
    assert event.summary == "samari"+sig
    assert event.payload["content"] == "halo i bims 1 alarm vong naemon her"


def test_example_runner_run_nodiscard_nosummary(setup):
    sig = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    runneropts = { "path": "/tmp", }
    _setup() # delete logfile
    eventopts = {
        "summary": "i bim dem sammari",
        "content": "halo i bims 1 alarm vong naemon her"+sig,
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  runneropts)
    example.handle(eventopts)
    log = open(get_logfile(example)).read()
    print("LOG="+log)
    assert "INFO - i bim dem sammari" in log
    echo = open("/tmp/echo").read()
    assert "halo i bims 1 alarm vong naemon her" in echo
    assert sig in echo

def test_example_runner_run_discard_loud(setup):
    runneropts = { "path": "/tmp", }
    _setup() # delete logfile
    eventopts = {
        "summary": "i bim dem sammari", # decider sets own summary
        "content": "halo i bims 1 alarm vong naemon her",
        "discard": False, # silently false: write discard: ..summary..
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  runneropts)
    #example.no_more_logging()
    example.handle(eventopts)
    log = open(get_logfile(example)).read()
    assert "discarded: halo i bims 1 alarm vong naemon her und i schmeis" in log
    assert not os.path.exists("/tmp/echo") # discard -> no runner

def test_example_runner_run_discard_silent(setup):
    runneropts = { "path": "/tmp", }
    _setup() # delete logfile
    eventopts = {
        "summary": "i bim dem sammari", # decider sets own summary
        "content": "halo i bims 1 alarm vong naemon her",
        "discard": True, # silently true: no logging at all
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  runneropts)
    #example.no_more_logging()
    example.handle(eventopts)
    log = open(get_logfile(example)).read()
    assert "discarded: halo i bims 1 alarm vong naemon her und i schmeis" not in log
    assert not os.path.exists("/tmp/echo") # discard -> no runner

def test_example_runner_timeout(setup):
    eventopts = {
        "summary": "i bim dem sammari", # decider sets own summary
        "content": "halo i bims 1 alarm vong naemon her",
        "discard": True, # silently true: no logging at all
        "delay": 120,
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  eventopts)
    example.handle(eventopts)
    assert not os.path.exists("/tmp/echo") # discard -> no runner

