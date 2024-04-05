import pytest
import http.server
import inspect
import sys
import os
import re
import time
import secrets
import base64
import string
import shutil
import hashlib, secrets
import logging
import subprocess
import threading
import json
import requests

omd_root = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = omd_root
if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(omd_root+"/pythonpath/local/lib/python")
    sys.path.append(omd_root+"/pythonpath/lib/python")
    sys.path.append(omd_root+"/../../notificationforwarder/src")
    os.environ["PYTHONPATH"] = ":".join(sys.path)

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
    if os.path.exists("/tmp/received_payload.json"):
        os.remove("/tmp/received_payload.json")
    if os.path.exists("/tmp/123"):
        os.remove("/tmp/123")

def get_logfile(forwarder):
    logger_name = "notificationforwarder_"+forwarder.name
    logger = logging.getLogger(logger_name)
    return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def check_auth(self):
        auth = self.headers.get('Authorization')
        if auth is None:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="consol"')
            self.end_headers()
            return False
        if auth.startswith("Basic "):
            basic_auth = base64.b64decode(auth[6:]).decode('utf-8')
            username, password = basic_auth.split(':', 1)
            if username == "i_bims" and password == "i_bims_1_i_bims":
                return True
            else:
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="consol"')
                self.end_headers()
                return False
        elif auth.startswith("Bearer "):
            token = auth[7:]
            if token == "i_bims_1_token":
                return True
            else:
                # Invalid token
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Bearer realm="consol"')
                self.end_headers()
                return False
        else:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="consol"')
            self.end_headers()
            return False

    def do_POST(self):
        headers = self.headers
        if not self.check_auth():
            return
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        with open('/tmp/received_payload.json', 'wb') as json_file:
            json_file.write(post_data)
        self.send_response(200)
        self.end_headers()

def start_server():
    server = http.server.HTTPServer(('localhost', 8080), RequestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return server

def stop_server(server):
    server.shutdown()
    server.server_close()

@pytest.fixture
def server_fixture(request):
    _setup()
    server = start_server()
    
    def fin():
        stop_server(server)

    request.addfinalizer(fin)
    return server








def test_eventhandler_success_notification(server_fixture):
    tic = time.time()
    random_string = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
    command = """PYTHONPATH=$PYTHONPATH OMD_SITE=my_devel_site OMD_ROOT={} {} \\
        --runner example \\
        --runnertag evthdl \\
        --runneropt echofile=/tmp/123 \\
        --decider example \\
        --eventopt HOSTNAME=vongsrv04 \\
        --eventopt HOSTSTATE=DOWN \\
        --eventopt NOTIFICATIONTYPE=PROBLEM \\
        --eventopt SERVICEDESC=some_service \\
        --eventopt content=ev_{} \\
        --eventopt delay=5 \\
        --eventopt summary=summsumm \\
        --forwarder webhook \\
        --forwarderopt url=http://localhost:8080 \\
        --forwarderopt username=i_bims \\
        --forwarderopt password=i_bims_1_i_bims \\
        --forwardertag evtnot \\
        --formatter eventhandler_report \\
        --eventopt description=i_describe_an_eventhandler \\
        --eventopt signature=no_{} \\
        2>&1 > /tmp/eventhandler_errors.log
    """.format(omd_root, os.environ["OMD_ROOT"]+"/../bin/eventhandler", random_string, random_string)
    run = subprocess.run(command, capture_output=True, shell=True)
    tac = time.time()
    print(run.__dict__) 
    assert run.returncode == 0
    # assert the eventhandler 
    assert os.path.exists("/tmp/123")
    with open("/tmp/123") as f:
        rndstr = f.read().strip()
    assert rndstr == "ev_"+random_string
    assert tac - tic >= 5
    assert os.path.exists(omd_root+"/var/log/eventhandler_example_evthdl.log")
    with open(omd_root+"/var/log/eventhandler_example_evthdl.log") as f:
        evtlog = f.read().strip()
    assert "INFO - summary is summsumm" in evtlog
    # assert the notificationhandler
    assert os.path.exists("/tmp/received_payload.json")
    with open('/tmp/received_payload.json') as f:
        payload = json.load(f)
    assert payload["signature"] == "no_"+random_string
    assert payload["description"] == "i_describe_an_eventhandler"
    assert os.path.exists(omd_root+"/var/log/notificationforwarder_webhook_evtnot.log")
    with open(omd_root+"/var/log/notificationforwarder_webhook_evtnot.log") as f:
        notlog = f.read().strip()
    assert "signature=no_"+random_string in notlog
    assert "eventhandler for vongsrv04/some_service succeeded" in notlog


def test_eventhandler_failure_notification(server_fixture):
    tic = time.time()
    random_string = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
    command = """PYTHONPATH=$PYTHONPATH OMD_SITE=my_devel_site OMD_ROOT={} {} \\
        --runner example \\
        --runnertag evthdl \\
        --runneropt echofile=/tmp/123/123/123 \\
        --decider example \\
        --eventopt HOSTNAME=vongsrv04 \\
        --eventopt HOSTSTATE=DOWN \\
        --eventopt NOTIFICATIONTYPE=PROBLEM \\
        --eventopt SERVICEDESC=some_service \\
        --eventopt content=ev_{} \\
        --eventopt delay=5 \\
        --eventopt summary=summsumm \\
        --forwarder webhook \\
        --forwarderopt url=http://localhost:8080 \\
        --forwarderopt username=i_bims \\
        --forwarderopt password=i_bims_1_i_bims \\
        --forwardertag evtnot \\
        --formatter eventhandler_report \\
        --eventopt description=i_describe_an_eventhandler \\
        --eventopt signature=no_{} \\
        2>&1 > /tmp/eventhandler_errors.log
    """.format(omd_root, os.environ["OMD_ROOT"]+"/../bin/eventhandler", random_string, random_string)
    run = subprocess.run(command, capture_output=True, shell=True)
    tac = time.time()
    print(run.__dict__) 
    assert run.returncode == 1
    # assert the eventhandler 
    assert not os.path.exists("/tmp/123")
    assert os.path.exists(omd_root+"/var/log/eventhandler_example_evthdl.log")
    with open(omd_root+"/var/log/eventhandler_example_evthdl.log") as f:
        evtlog = f.read().strip()
    assert "CRITICAL - run failed" in evtlog
    assert "cannot create /tmp/123/123/123" in evtlog
    # assert the notificationhandler
    assert os.path.exists("/tmp/received_payload.json")
    with open('/tmp/received_payload.json') as f:
        payload = json.load(f)
    assert payload["signature"] == "no_"+random_string
    assert payload["description"] == "i_describe_an_eventhandler"
    assert os.path.exists(omd_root+"/var/log/notificationforwarder_webhook_evtnot.log")
    with open(omd_root+"/var/log/notificationforwarder_webhook_evtnot.log") as f:
        notlog = f.read().strip()
    assert "signature=no_"+random_string in notlog
    assert "eventhandler for vongsrv04/some_service failed" in notlog


