import pytest
import os
import re
import time
import shutil
import hashlib, secrets
import eventhandler.baseclass
import logging
os.environ['PYTHONDONTWRITEBYTECODE'] = "true"

def _setup():
    omd_root = os.path.dirname(__file__)
    os.environ["OMD_ROOT"] = omd_root
    shutil.rmtree(omd_root+"/var", ignore_errors=True)
    os.makedirs(omd_root+"/var/log", 0o755)
    shutil.rmtree(omd_root+"/var", ignore_errors=True)
    os.makedirs(omd_root+"/var/tmp", 0o755)
    shutil.rmtree(omd_root+"/tmp", ignore_errors=True)
    os.makedirs(omd_root+"/tmp", 0o755)
    if os.path.exists("/tmp/eventhandler_example.txt"):
        os.remove("/tmp/eventhandler_example.txt")

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
    fexample = example.new_decider()
    assert fexample.__class__.__name__ == "ExampleDecider"


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
    example = eventhandler.baseclass.new("example", None, "example", True, True,  {})
    fexample = example.new_decider()
    raw_event = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    event = eventhandler.baseclass.DecidedEvent(raw_event)
    assert event.eventopts["description"] == "halo i bims 1 alarm vong naemon her"
    fexample.decide_and_prepare(event)
    print(fexample)
    print(fexample.__dict__)
    assert event.summary == "halo i bims 1 alarm vong naemon her und i schmeis mi weg"
    assert event.payload["cmd"] == "echo"
    assert event.payload["parameters"] == "halo i bims 1 alarm vong naemon her"
    assert event.payload["timestamp"] == pytest.approx(time.time(), abs=5)


def test_example_runner_forward(setup):
    reveiveropts = {
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  reveiveropts)
    example.forward(eventopts)
    log = open(get_logfile(example)).read()
    assert "INFO - i_bims submits" in log
    assert "'description': 'halo i bims 1 alarm vong naemon her'" in log
    # this is the global log, written by the baseclass
    assert "INFO - forwarded sum: halo i bims 1 alarm vong naemon her" in log

    _setup() # delete logfile
    # we need to reinitialize, because the logger has the (deleted) file
    # still open and further writes would end up in nirvana.
    example = eventhandler.baseclass.new("example", None, "example", True, True,  reveiveropts)
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her again",
    }
    example.no_more_logging()
    example.forward(eventopts)
    log = open(get_logfile(example)).read()
    # the decider's logs are still there
    assert "INFO - i_bims submits" in log
    assert "'description': 'halo i bims 1 alarm vong naemon her again'" in log
    # but not the baseclasse's log
    assert "INFO - forwarded sum: halo i bims 1 alarm vong naemon her" not in log

def test_example_runner_forward_success(setup):
    reveiveropts = {
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
        "signature": signature,
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  reveiveropts)
    example.forward(eventopts)
    assert os.path.exists(example.signaturefile)
    sig = open(example.signaturefile).read().strip()
    assert sig == signature

def test_example_runner_forward_timeout(setup):
    signatures = [
        hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
        hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
        hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
    ]
    reveiveropts = {
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
        "delay": 60,
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
        "signature": signatures[0],
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  reveiveropts)
    example.forward(eventopts)
    log = open(get_logfile(example)).read()
    # this is the global log, written by the baseclass
    assert "submit ran into a timeout" in log
    assert "spooled <sum: halo i bims 1 alarm vong naemon her>" in log
    assert "WARNING - spooling queue length is 1" in log
    eventopts = {
        "description": "halo i bim au 1 alarm vong naemon her",
        "signature": signatures[1],
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  reveiveropts)
    example.forward(eventopts)
    log = open(get_logfile(example)).read()
    assert "spooled <sum: halo i bim au 1 alarm vong naemon her>" in log
    assert "WARNING - spooling queue length is 2" in log
    # now the last two events were spooled and are in the database

    reveiveropts = {
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
        "delay": 0,
    }
    eventopts = {
        "description": "i druecke dem spuelung",
        "signature": signatures[2],
    }
    example = eventhandler.baseclass.new("example", None, "example", True, True,  reveiveropts)
    example.forward(eventopts)
    log = open(get_logfile(example)).read()
    assert re.search(r'.*i_bims submits.*i druecke dem spuelung.*', log, re.MULTILINE)
    assert "forwarded sum: i druecke dem spuelung" in log
    assert "DEBUG - flush lock set" in log
    assert "INFO - there are 2 spooled events to be re-sent" in log
    assert "INFO - delete spooled event 1" in log
    assert "INFO - delete spooled event 2" in log
    assert re.search(r'.*i_bims submits.*halo i bims 1 alarm vong naemon her.*', log, re.MULTILINE)
    assert re.search(r'.*i_bims submits.*halo i bim au 1 alarm vong naemon her.*', log, re.MULTILINE)
    sigs = [l.strip() for l in open(example.signaturefile).readlines()]
    # flushing first, then the new event
    assert sigs == signatures
