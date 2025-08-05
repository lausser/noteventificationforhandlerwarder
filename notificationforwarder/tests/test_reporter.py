import pytest
#OMD_SITE=my_devel_site PYTHONPATH=`pwd`/src bin/notificationforwarder --eventopt HOSTNAME=kak --eventopt HOSTSTATE=UP --eventopt HOSTOUTPUT="kak"  --reporter naemonlog --reporteropt api=cmd --forwarderopt port=123 --eventopt SERVICEDESC="show the kak of kak" --eventopt SERVICESTATE=CRITICAL --eventopt SERVICEOUTPUT="i bin kak"

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
import pathlib


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
    if os.path.exists(omd_root+"/var/tmp/naemon.cmd"):
        os.remove(omd_root+"/var/tmp/naemon.cmd")

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


def test_forward_webhook_format_vong_bin_basic_auth(server_fixture):
    forwarderopts = {
        "url": "http://localhost:8080",
        "username": "i_bims",
        "password": "i_bims_1_i_bims",
    }   
    eventopts = {
        "HOSTNAME": "vongsrv02",
        "HOSTSTATE": "DOWN",
        "HOSTOUTPUT": "aechz",
        "NOTIFICATIONTYPE": "PROBLEM",
        "CONTACTNAME": "da_daepp",
        "NOTIFICATIONCOMMAND": "kommando_pimperle",
    }
    webhook = notificationforwarder.baseclass.new("webhook", None, "vong", True, True,  forwarderopts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    command_file = os.environ["OMD_ROOT"]+"/var/tmp/naemon.cmd"
    pathlib.Path(command_file).touch()
    forwarderoptsparams = " ".join(["--forwarderopt {}='{}'".format(k, v) for k, v in forwarderopts.items()])
    eventoptsparams = " ".join(["--eventopt {}='{}'".format(k, v) for k, v in eventopts.items()])
    print("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {} --reporter naemonlog --reporteropt command_file={}".format(omd_root, pythonpath, cmd, forwarderoptsparams, eventoptsparams, command_file))
    subprocess.call("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {} --reporter naemonlog --reporteropt command_file={}".format(omd_root, pythonpath, cmd, forwarderoptsparams, eventoptsparams, command_file), shell=True)
    log = open(get_logfile(webhook)).read()
    with open("/tmp/received_payload.json") as f:
        payload = f.read()
    payload = json.loads(payload)
    assert payload["host_name"] == "vongsrv02"
    with open(command_file) as f:
        naemonlog = f.read()
    assert "HOST NOTIFICATION: da_daepp;vongsrv02;kommando_pimperle;DOWN;aechz" in naemonlog

def test_forward_webhook_format_vong_bin_basic_auth_fail(server_fixture):
    forwarderopts = {
        "url": "http://localhost:8080",
        "username": "i_bims",
        "password": "i_bums_1_i_bums",
    }   
    eventopts = {
        "HOSTNAME": "vongsrv02",
        "HOSTSTATE": "DOWN",
        "HOSTOUTPUT": "aechz",
        "NOTIFICATIONTYPE": "PROBLEM",
        #"CONTACTNAME": default GLOBAL
        #"NOTIFICATIONCOMMAND": default global_host_notification_handler
    }
    webhook = notificationforwarder.baseclass.new("webhook", None, "vong", True, True,  forwarderopts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    command_file = os.environ["OMD_ROOT"]+"/var/tmp/naemon.cmd"
    pathlib.Path(command_file).touch()
    forwarderoptsparams = " ".join(["--forwarderopt {}='{}'".format(k, v) for k, v in forwarderopts.items()])
    eventoptsparams = " ".join(["--eventopt {}='{}'".format(k, v) for k, v in eventopts.items()])
    print("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {} --reporter naemonlog --reporteropt command_file={}".format(omd_root, pythonpath, cmd, forwarderoptsparams, eventoptsparams, command_file))
    subprocess.call("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder webhook {} --formatter vong {} --reporter naemonlog --reporteropt command_file={}".format(omd_root, pythonpath, cmd, forwarderoptsparams, eventoptsparams, command_file), shell=True)
    log = open(get_logfile(webhook)).read()
    assert not os.path.exists("/tmp/received_payload.json")
    with open(command_file) as f:
        naemonlog = f.read()
    assert "HOST NOTIFICATION: GLOBAL;vongsrv02;global_host_notification_handler;DOWN;aechz (could not be forwarded to webhook)" in naemonlog

def test_reporter_payload_ok(server_fixture):
    forwarderopts = {
        "signature": "wrdlbrmpft"
    }
    eventopts = {
        "HOSTNAME": "vongsrv02",
        "HOSTSTATE": "DOWN",
        "HOSTOUTPUT": "aechz",
        "NOTIFICATIONTYPE": "PROBLEM",
    }
    cm = notificationforwarder.baseclass.new("ticketsystem", None, "vong", True, True,  forwarderopts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    command_file = os.environ["OMD_ROOT"]+"/var/tmp/naemon.cmd"
    assert not os.path.exists(command_file)
    pathlib.Path(command_file).touch()
    forwarderoptsparams = " ".join(["--forwarderopt {}='{}'".format(k, v) for k, v in forwarderopts.items()])
    eventoptsparams = " ".join(["--eventopt {}='{}'".format(k, v) for k, v in eventopts.items()])
    print("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder ticketsystem {} --formatter vong {} --reporter naemonlog --reporteropt command_file={}".format(omd_root, pythonpath, cmd, forwarderoptsparams, eventoptsparams, command_file))
    subprocess.call("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder ticketsystem {} --formatter vong {} --reporter ticketsystem --reporteropt command_file={}".format(omd_root, pythonpath, cmd, forwarderoptsparams, eventoptsparams, command_file), shell=True)
    log = open(get_logfile(cm)).read()
    assert not os.path.exists("/tmp/received_payload.json")
    with open(command_file) as f:
        naemonlog = f.read()
    assert "HOST NOTIFICATION: GLOBAL;vongsrv02;global_host_notification_handler;DOWN;aechz created INC00000000/wrdlbrmpft" in naemonlog

def test_reporter_payload_fail(server_fixture):
    forwarderopts = {
        "nosignature": "wrdlbrmpft"
    }
    eventopts = {
        "HOSTNAME": "vongsrv02",
        "HOSTSTATE": "DOWN",
        "HOSTOUTPUT": "aechz",
        "NOTIFICATIONTYPE": "PROBLEM",
    }
    cm = notificationforwarder.baseclass.new("ticketsystem", None, "vong", True, True,  forwarderopts)
    pythonpath = os.environ["OMD_ROOT"]+"/../src:"+os.environ["OMD_ROOT"]+"/pythonpath/local/lib/python"+":"+os.environ["OMD_ROOT"]+"/pythonpath/lib/python"
    cmd = os.environ["OMD_ROOT"]+"/../bin/notificationforwarder"
    command_file = os.environ["OMD_ROOT"]+"/var/tmp/naemon.cmd"
    assert not os.path.exists(command_file)
    pathlib.Path(command_file).touch()
    forwarderoptsparams = " ".join(["--forwarderopt {}='{}'".format(k, v) for k, v in forwarderopts.items()])
    eventoptsparams = " ".join(["--eventopt {}='{}'".format(k, v) for k, v in eventopts.items()])
    print("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder ticketsystem {} --formatter vong {} --reporter naemonlog --reporteropt command_file={}".format(omd_root, pythonpath, cmd, forwarderoptsparams, eventoptsparams, command_file))
    subprocess.call("OMD_SITE=my_devel_site OMD_ROOT={} PYTHONPATH={} {} --forwarder ticketsystem {} --formatter vong {} --reporter ticketsystem --reporteropt command_file={}".format(omd_root, pythonpath, cmd, forwarderoptsparams, eventoptsparams, command_file), shell=True)
    log = open(get_logfile(cm)).read()
    assert not os.path.exists("/tmp/received_payload.json")
    with open(command_file) as f:
        naemonlog = f.read()
    assert "HOST NOTIFICATION: GLOBAL;vongsrv02;global_host_notification_handler;DOWN;aechz (could not be forwarded to ticketsystem)" in naemonlog
