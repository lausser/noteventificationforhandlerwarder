import pytest
import http.server
import inspect
import sys
import os
import re
import shutil
import hashlib, secrets
import logging
import subprocess
import threading
import json
import requests
import hashlib, secrets
import base64


omd_root = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = omd_root
if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/lib/python")
    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/../src")
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
    if os.path.exists("/tmp/received_payload.json"):
        os.remove("/tmp/received_payload.json")

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

def xtest_send_json_payload_to_server(server_fixture):
    url = "http://localhost:8080"
    data = {"key": "value", "another_key": "another_value"}

    response = requests.post(url, json=data)
    assert response.status_code == 200

    with open('/tmp/received_payload.json', 'rb') as json_file:
        saved_payload = json.load(json_file)

    assert saved_payload == data

def test_forward_webhook_format_rabbitmq(server_fixture):
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    reveiveropts = {
        "url": "http://localhost:8080/api/v1",
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }   
    eventopts = {
        "HOSTNAME": "vongsrv01",
        "NOTIFICATIONTYPE": "PROBLEM",
        "HOSTSTATE": "DOWN",
        "HOSTOUTPUT": "i bim der host un mir is schlecht i kotz hex "+signature,
        "description": "halo i bims 1 alarm vong naemon her",
    }

    webhook = notificationforwarder.baseclass.new("webhook", None, "rabbitmq", True, True,  reveiveropts)
    webhook.forward(eventopts)
    log = open(get_logfile(webhook)).read()
    assert "INFO - success:" in log 
    assert signature in log 
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert payload[0]["output"] == "i bim der host un mir is schlecht i kotz hex "+signature

def test_forward_webhook_format_example(server_fixture):
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    reveiveropts = {
        "url": "http://localhost:8080",
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }   
    eventopts = {
        "signature": signature,
        "description": "halo i bims 1 alarm vong naemon her",
    }

    webhook = notificationforwarder.baseclass.new("webhook", None, "example", True, True,  reveiveropts)
    webhook.forward(eventopts)
    log = open(get_logfile(webhook)).read()
    assert "INFO - success: sum: "+eventopts["description"] in log 
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert payload["signature"] == signature
    assert payload["description"] == eventopts["description"]
    assert "timestamp" in payload

def test_forward_webhook_format_vong(server_fixture):
    reveiveropts = {
        "url": "http://localhost:8080",
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }   
    eventopts = {
        "HOSTNAME": "vongsrv01",
        "HOSTSTATE": "DOWN",
        "NOTIFICATIONTYPE": "PROBLEM",
    }

    webhook = notificationforwarder.baseclass.new("webhook", None, "vong", True, True,  reveiveropts)
    webhook.forward(eventopts)
    log = open(get_logfile(webhook)).read()
    assert "INFO - success: i hab dem post gepost" in log 
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert "host_name" in payload

def test_forward_webhook_format_bayern(server_fixture):
    reveiveropts = {
        "url": "http://localhost:8080",
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }   
    eventopts = {
        "HOSTNAME": "seppsrv01",
        "HOSTSTATE": "DOWN",
        "NOTIFICATIONTYPE": "PROBLEM",
    }

    webhook = notificationforwarder.baseclass.new("webhook", None, "bayern", True, True,  reveiveropts)
    webhook.forward(eventopts)
    log = open(get_logfile(webhook)).read()
    assert "INFO - success: des glump {} is hi".format(eventopts["HOSTNAME"]) in log
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert "da_host" in payload

def test_forward_webhook_format_vong_bin_basic_auth(server_fixture):
    reveiveropts = {
        "url": "http://localhost:8080",
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }   
    eventopts = {
        "HOSTNAME": "vongsrv02",
        "HOSTSTATE": "DOWN",
        "NOTIFICATIONTYPE": "PROBLEM",
    }
    webhook = notificationforwarder.baseclass.new("webhook", None, "vong", True, True,  reveiveropts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    reveiveroptsparams = " ".join(["--forwarderopt {}='{}'".format(k, v) for k, v in reveiveropts.items()])
    eventoptsparams = " ".join(["--eventopt {}='{}'".format(k, v) for k, v in eventopts.items()])
    print("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {}".format(omd_root, pythonpath, cmd, reveiveroptsparams, eventoptsparams))
    subprocess.call("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {}".format(omd_root, pythonpath, cmd, reveiveroptsparams, eventoptsparams), shell=True)
    log = open(get_logfile(webhook)).read()
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert payload["host_name"] == "vongsrv02"

def test_forward_webhook_format_vong_bin_token_auth(server_fixture):
    # auth with token, token is in forwarderopts
    reveiveropts = {
        "url": "http://localhost:8080",
        "headers": '{"Authorization": "Bearer i_bims_1_token"}',
    }   
    eventopts = {
        "HOSTNAME": "vongsrv03",
        "HOSTSTATE": "DOWN",
        "NOTIFICATIONTYPE": "PROBLEM",
    }
    webhook = notificationforwarder.baseclass.new("webhook", None, "vong", True, True,  reveiveropts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    reveiveroptsparams = " ".join(["--forwarderopt {}='{}'".format(k, v) for k, v in reveiveropts.items()])
    eventoptsparams = " ".join(["--eventopt {}='{}'".format(k, v) for k, v in eventopts.items()])
    print("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {}".format(omd_root, pythonpath, cmd, reveiveroptsparams, eventoptsparams))
    subprocess.call("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {}".format(omd_root, pythonpath, cmd, reveiveroptsparams, eventoptsparams), shell=True)
    #raise
    log = open(get_logfile(webhook)).read()
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert payload["host_name"] == "vongsrv03"

def test_forward_webhook_format_vong_bin_token_auth_by_formatter(server_fixture):
    # auth with token, token is created by the formatter
    reveiveropts = {
        "url": "http://localhost:8080",
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }   
    eventopts = {
        "HOSTNAME": "vongsrv04",
        "HOSTSTATE": "DOWN",
        "NOTIFICATIONTYPE": "PROBLEM",
        # if this key exists, then the formatter fills the header
        # event.forwarderopts["headers"] = '{{"Authorization":
        "dem_is_geheim": "i_bims_1_token",
    }
    webhook = notificationforwarder.baseclass.new("webhook", None, "vong", True, True,  reveiveropts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    reveiveroptsparams = " ".join(["--forwarderopt {}='{}'".format(k, v) for k, v in reveiveropts.items()])
    eventoptsparams = " ".join(["--eventopt {}='{}'".format(k, v) for k, v in eventopts.items()])
    print("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {}".format(omd_root, pythonpath, cmd, reveiveroptsparams, eventoptsparams))
    subprocess.call("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {}".format(omd_root, pythonpath, cmd, reveiveroptsparams, eventoptsparams), shell=True)
    log = open(get_logfile(webhook)).read()
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert payload["host_name"] == "vongsrv04"

