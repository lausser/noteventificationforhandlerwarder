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


omd_root = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = omd_root
#if not [p for p in sys.path if "pythonpath" in p]:
#    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python")
#    sys.path.append(os.environ["OMD_ROOT"]+"/pythonpath/lib/python")
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
    def checkAuthentication(self):
        auth = self.headers.get('Authorization')
        if auth != "Basic %s" % self.server.auth:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="webiopi"')
            self.end_headers();
            return False
        return True

    def do_POST(self):
        if not self.checkAuthentication():
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

def test_send_json_payload_to_server(server_fixture):
    url = "http://localhost:8080"
    data = {"key": "value", "another_key": "another_value"}

    response = requests.post(url, json=data)
    assert response.status_code == 200

    with open('/tmp/received_payload.json', 'rb') as json_file:
        saved_payload = json.load(json_file)

    assert saved_payload == data

def test_webhook_forward_rabbitmq(server_fixture):
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    reveiveropts = {
        "url": "http://localhost:8080"
        #"username": "i_bims",
        #"password": "i_bims_1_i_bims",
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
    assert "INFO - forwarded" in log 
    assert signature in log 
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert payload[0]["output"] == "i bim der host un mir is schlecht i kotz hex "+signature

def test_webhook_forward_example(server_fixture):
    signature = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    reveiveropts = {
        "url": "http://localhost:8080"
        #"username": "i_bims",
        #"password": "i_bims_1_i_bims",
    }   
    eventopts = {
        "signature": signature,
        "description": "halo i bims 1 alarm vong naemon her",
    }

    webhook = notificationforwarder.baseclass.new("webhook", None, "example", True, True,  reveiveropts)
    webhook.forward(eventopts)
    log = open(get_logfile(webhook)).read()
    assert "INFO - forwarded sum: "+eventopts["description"] in log 
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert payload["signature"] == signature
    assert payload["description"] == eventopts["description"]
    assert "timestamp" in payload


