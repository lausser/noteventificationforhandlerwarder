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
    sys.path.append(omd_root+"/pythonpath/local/lib/python")
    sys.path.append(omd_root+"/pythonpath/lib/python")
    sys.path.append(omd_root+"/pythonpath/../src")
    sys.path.append(omd_root+"/../../notificationforwarder/src")
    print("PYTHONPATH="+":".join(sys.path))
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








def test_th_formatter(server_fixture):
    #pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"

    command = """echo PYTHONPATH=$PYTHONPATH OMD_SITE=my_devel_site OMD_ROOT={} {} \\
        --runner example \\
        --runnertag evtnot \\
        --runneropt echofile=/tmp/123 \\
        --decider eaxmple \\
        --eventopt HOSTNAME=vongsrv04 \\
        --eventopt HOSTSTATE=DOWN \\
        --eventopt NOTIFICATIONTYPE=PROBLEM \\
        --debug \\
        2>&1 > /tmp/eventhandler_errors.log \\
    """.format(omd_root, os.environ["OMD_ROOT"]+"/../bin/eventhandler")
# --forwarder webhook/example -> /tmp/123
    print(sys.path)
    print(command)



    subprocess.call(command, shell=True)
#    log = open(get_logfile(webhook)).read()
#    with open("/tmp/received_payload.json") as f:
#        payload = f.read()
#    payload = json.loads(payload)
#    assert payload["host_name"] == "vongsrv04"

