import pytest
import requests
import time
import sys
import os
import threading
import http.server
import socket
import re
import json
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


def test_alertmanager_forwarder(setup):
    def serve_requests():
        import http.server
        import socketserver

        class RequestHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Hello, World!')
            def do_POST(self):
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                self.send_response(200)
                self.end_headers()
                post_data_dict = json.loads(post_data.decode('utf-8'))
                self.wfile.write(json.dumps({"status": "ok", "records": len(post_data_dict["records"])}).encode('utf-8'))

        # Create an HTTP server
        server = socketserver.TCPServer(('localhost', 0), RequestHandler)

        # Start serving requests in a separate thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        return server


    http_server = serve_requests()

    # Get the server address and port
    address, port = http_server.server_address

    forwarderopts = {
        "url": f"http://{address}:{port}/",
        "username": "i_bims",
        "password": "dem_is_geheim"
    }
    eventopts = {
        "alertmanager_payload": {
            "receiver": "omd-servicenow-webhook",
            "status": "firing",
            "alerts": [
              {
                "status": "firing",
                "labels": {
                  "alertname": "4490",
                  "instance": "4490.example.net",
                  "service": "my-service",
                  "severity": "critical",
                  "snow_service_name": "routemetosvcnow"
                },
                "annotations": {
                  "summary": "Testing summary!"
                },
                "startsAt": "2024-03-15T19:51:51.78480206Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "https://prometheus.local/<generating_expression>",
                "fingerprint": "5de8a3a5c73e68d4"
              },
              {
                "status": "firing",
                "labels": {
                  "alertname": "4491",
                  "instance": "4491.example.net",
                  "service": "my-other-service",
                  "severity": "critical",
                  "snow_service_name": "routemetosvcnow"
                },
                "annotations": {
                  "summary": "Testing summary!"
                },
                "startsAt": "2024-03-15T19:51:51.78480206Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "https://prometheus.local/<generating_expression>",
                "fingerprint": "5de8a3a5c73e68d5"
              }
            ],
            "groupLabels": {
              "alertname": "4490",
              "service": "my-service"
            },
            "commonLabels": {
              "alertname": "4490",
              "instance": "4490.example.net",
              "service": "my-service",
              "severity": "critical",
              "snow_service_name": "routemetosvcnow"
            },
            "commonAnnotations": {
              "summary": "Testing summary!"
            },
            "externalURL": "http://omd-lx01.example.com/alertmanager/alertmanager",
            "version": "4",
            "groupKey": "{}/{alertname=~\"^(?:.*)$\",snow_service_name=~\"^(?:..*)$\"}:{alertname=\"4490\", service=\"my-service\"}",
            "truncatedAlerts": 0
        }
    }


    amgw = notificationforwarder.baseclass.new("webhook", None, "alertmanager_servicenow", False, False,  forwarderopts)
    famgw = amgw.new_formatter()
    assert famgw.__class__.__name__ == "AlertmanagerServicenowFormatter"
    assert famgw.__module_file__.endswith("pythonpath/local/lib/python/notificationforwarder/alertmanager_servicenow/formatter.py")
    assert type(eventopts) == dict
    assert type(eventopts["alertmanager_payload"]) == dict

    amgw.forward(eventopts)
    log = open(get_logfile(amgw)).read()
    assert re.search(r'success: alertmanager sends 2 alarms.*result is .*"records": 2.*4490.*4491.*', log, flags=re.MULTILINE)

    http_server.shutdown()



