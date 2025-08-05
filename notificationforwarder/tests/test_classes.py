import pytest
import os
import re
import time
import shutil
import hashlib, secrets
import notificationforwarder.baseclass
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


def test_example_forwarder(setup):
    forwarderopts = {
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  forwarderopts)
    assert example.__class__.__name__ == "ExampleForwarder"
    assert example.password == "dem_is_geheim"
    assert example.queued_events == []


def _test_example_formatter(setup):
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  {})
    fexample = example.new_formatter()
    assert fexample.__class__.__name__ == "ExampleFormatter"


def test_example_logging(setup):
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  {})
    logger_name = "notificationforwarder_"+example.name
    logger = logging.getLogger(logger_name)
    assert logger != None
    assert logger.name == "notificationforwarder_example"
    assert len([h for h in logger.handlers]) == 2
    logfile = [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]
    assert logfile.endswith("notificationforwarder_example.log")

    example = notificationforwarder.baseclass.new("example", "2", "example", True, True,  {})
    logger_name = "notificationforwarder_"+example.name+"_"+example.tag
    logger = logging.getLogger(logger_name)
    assert logger != None
    assert logger.name == "notificationforwarder_example_2"
    assert len(logger.handlers) == 2
    logfile = [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]
    assert logfile.endswith("notificationforwarder_example_2.log")
    

def test_example_formatter_format_event(setup):
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  {})
    fexample = example.new_formatter()
    raw_event = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    event = notificationforwarder.baseclass.FormattedEvent(raw_event)
    assert event.eventopts["description"] == "halo i bims 1 alarm vong naemon her"
    fexample.format_event(event)
    assert event.summary == "sum: halo i bims 1 alarm vong naemon her"
    assert event.payload["description"] == "halo i bims 1 alarm vong naemon her"
    assert event.payload["timestamp"] == pytest.approx(time.time(), abs=5)


def test_example_forwarder_forward(setup):
    forwarderopts = {
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
    }
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  forwarderopts)
    example.forward(eventopts)
    log = open(get_logfile(example)).read()
    assert "INFO - i_bims submits" in log
    assert "'description': 'halo i bims 1 alarm vong naemon her'" in log
    # this is the global log, written by the baseclass
    assert "INFO - forwarded sum: halo i bims 1 alarm vong naemon her" in log

    _setup() # delete logfile
    # we need to reinitialize, because the logger has the (deleted) file
    # still open and further writes would end up in nirvana.
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  forwarderopts)
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her again",
    }
    example.no_more_logging()
    example.forward(eventopts)
    log = open(get_logfile(example)).read()
    # the formatter's logs are still there
    assert "INFO - i_bims submits" in log
    assert "'description': 'halo i bims 1 alarm vong naemon her again'" in log
    # but not the baseclasse's log
    assert "INFO - forwarded sum: halo i bims 1 alarm vong naemon her" not in log

def test_example_forwarder_forward_success(setup):
    forwarderopts = {
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
        "signature": signature,
    }
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  forwarderopts)
    example.forward(eventopts)
    assert os.path.exists(example.signaturefile)
    sig = open(example.signaturefile).read().strip()
    assert sig == signature

def test_example_forwarder_forward_timeout(setup):
    signatures = [
        hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
        hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
        hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
    ]
    forwarderopts = {
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
        "delay": 60,
    }
    eventopts = {
        "description": "halo i bims 1 alarm vong naemon her",
        "signature": signatures[0],
    }
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  forwarderopts)
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
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  forwarderopts)
    example.forward(eventopts)
    log = open(get_logfile(example)).read()
    assert "spooled <sum: halo i bim au 1 alarm vong naemon her>" in log
    assert "WARNING - spooling queue length is 2" in log
    # now the last two events were spooled and are in the database

    forwarderopts = {
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
        "delay": 0,
    }
    eventopts = {
        "description": "i druecke dem spuelung",
        "signature": signatures[2],
    }
    example = notificationforwarder.baseclass.new("example", None, "example", True, True,  forwarderopts)
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
