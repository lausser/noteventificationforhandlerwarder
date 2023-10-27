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
    start_server()

@pytest.fixture
def setup():
    _setup()
    yield

def get_logfile(forwarder):
    logger_name = "notificationforwarder_"+forwarder.name
    logger = logging.getLogger(logger_name)
    return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


class JSONRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        with open('received_payload.json', 'wb') as json_file:
            json_file.write(post_data)

        self.send_response(200)
        self.end_headers()

def start_server():
    server = http.server.HTTPServer(('localhost', 8080), JSONRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()


def test_send_json_payload_to_server(setup):
    url = "http://localhost:8080"
    data = {"key": "value", "another_key": "another_value"}

    response = requests.post(url, json=data)
    assert response.status_code == 200

    with open('received_payload.json', 'rb') as json_file:
        saved_payload = json.load(json_file)

    assert saved_payload == data


