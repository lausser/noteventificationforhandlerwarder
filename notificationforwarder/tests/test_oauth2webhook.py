import pytest
import http.server
import sys
import os
import shutil
import json
import time
import logging
import threading
import requests

omd_root = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = omd_root
if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/../src")

import notificationforwarder.baseclass

TOKEN_PORT = 18900
API_PORT = 18901
VALID_TOKEN = "test_bearer_token_xyz"
CLIENT_ID = "my_client_id"
CLIENT_SECRET = "my_client_secret"


def _setup():
    global omd_root
    omd_root = os.path.dirname(__file__)
    os.environ["OMD_ROOT"] = omd_root
    shutil.rmtree(omd_root + "/var", ignore_errors=True)
    os.makedirs(omd_root + "/var/log", 0o755)
    os.makedirs(omd_root + "/var/tmp", 0o755)
    shutil.rmtree(omd_root + "/tmp", ignore_errors=True)
    os.makedirs(omd_root + "/tmp", 0o755)
    # Remove stale token cache files
    for f in os.listdir(omd_root):
        if f.endswith("_oauth2token.json") or f.endswith("_oauth2token.json.lock"):
            os.remove(os.path.join(omd_root, f))


def get_logfile(forwarder):
    logger_name = "notificationforwarder_" + forwarder.forwarder_name
    log = logging.getLogger(logger_name)
    return [h.baseFilename for h in log.handlers if hasattr(h, "baseFilename")][0]


# Counters shared between test and server threads
token_requests = {"count": 0}
api_requests = {"count": 0, "last_auth": None}


class DualHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # suppress access log noise

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()

        if self.path == "/oauth/accesstoken/v2":
            token_requests["count"] += 1
            import urllib.parse
            params = dict(urllib.parse.parse_qsl(body))
            if (params.get("client_id") == CLIENT_ID and
                    params.get("client_secret") == CLIENT_SECRET and
                    params.get("grant_type") == "client_credentials"):
                response = json.dumps({
                    "access_token": VALID_TOKEN,
                    "expires_in": 3600,
                    "token_type": "Bearer",
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
            else:
                self.send_response(401)
                self.end_headers()

        elif self.path.startswith("/api/"):
            api_requests["count"] += 1
            auth = self.headers.get("Authorization", "")
            api_requests["last_auth"] = auth
            if auth == "Bearer {}".format(VALID_TOKEN):
                self.send_response(200)
                self.end_headers()
            else:
                self.send_response(401)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def start_combined_server(port):
    server = http.server.HTTPServer(("localhost", port), DualHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    return server


@pytest.fixture
def server_fixture(request):
    _setup()
    token_requests["count"] = 0
    api_requests["count"] = 0
    api_requests["last_auth"] = None

    # Use a single server on TOKEN_PORT that handles both paths
    server = start_combined_server(TOKEN_PORT)

    def fin():
        server.shutdown()
        server.server_close()

    request.addfinalizer(fin)
    return server


def make_forwarder(tag=None, extra_opts=None):
    opts = {
        "url": "http://localhost:{}/api/events".format(TOKEN_PORT),
        "token_url": "http://localhost:{}/oauth/accesstoken/v2".format(TOKEN_PORT),
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    if extra_opts:
        opts.update(extra_opts)
    return notificationforwarder.baseclass.new("oauth2webhook", tag, "example", True, True, opts)


def make_event():
    return {
        "HOSTNAME": "testhost",
        "NOTIFICATIONTYPE": "PROBLEM",
        "HOSTSTATE": "DOWN",
        "description": "test alert",
    }


def test_token_acquired_and_used(server_fixture):
    fw = make_forwarder()
    fw.forward(make_event())
    assert token_requests["count"] == 1
    assert api_requests["last_auth"] == "Bearer {}".format(VALID_TOKEN)
    log = open(get_logfile(fw)).read()
    assert "CRITICAL" not in log


def test_cached_token_reused(server_fixture):
    fw = make_forwarder()
    # Pre-populate the cache with a fresh token
    cache_path = fw._token_cache_path()
    with open(cache_path, "w") as f:
        json.dump({"access_token": VALID_TOKEN, "expires_at": time.time() + 3600}, f)

    fw.forward(make_event())
    # Token endpoint must NOT be called — cache was valid
    assert token_requests["count"] == 0
    assert api_requests["last_auth"] == "Bearer {}".format(VALID_TOKEN)


def test_expired_cache_triggers_refresh(server_fixture):
    fw = make_forwarder()
    # Write an already-expired token to cache
    cache_path = fw._token_cache_path()
    with open(cache_path, "w") as f:
        json.dump({"access_token": "old_token", "expires_at": time.time() - 10}, f)

    fw.forward(make_event())
    # Token endpoint must be called to refresh
    assert token_requests["count"] == 1
    assert api_requests["last_auth"] == "Bearer {}".format(VALID_TOKEN)


def test_token_failure_spools_event(server_fixture):
    # Point token_url at a non-existent endpoint so acquisition fails
    fw = notificationforwarder.baseclass.new(
        "oauth2webhook", None, "example", True, True, {
            "url": "http://localhost:{}/api/events".format(TOKEN_PORT),
            "token_url": "http://localhost:{}/oauth/does_not_exist".format(TOKEN_PORT),
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
    )
    fw.forward(make_event())
    # API must NOT have been called
    assert api_requests["count"] == 0
    # Event must have been spooled
    import sqlite3
    conn = sqlite3.connect(fw.db_file)
    rows = conn.execute("SELECT COUNT(*) FROM {}".format(fw.table_name)).fetchone()[0]
    conn.close()
    assert rows == 1


def test_tag_separates_token_cache(server_fixture):
    fw1 = make_forwarder(tag="prod")
    fw2 = make_forwarder(tag="staging")
    assert fw1._token_cache_path() != fw2._token_cache_path()
    assert "prod" in fw1._token_cache_path()
    assert "staging" in fw2._token_cache_path()
