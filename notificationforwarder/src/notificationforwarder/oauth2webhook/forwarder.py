import json
import os
import time
import fcntl
import requests
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

import notificationforwarder.webhook.forwarder as _webhook_module
from notificationforwarder.webhook.forwarder import WebhookForwarder
from notificationforwarder.baseclass import NotificationForwarder, timeout

logger = None


class Oauth2WebhookForwarder(WebhookForwarder):
    def __init__(self, opts):
        # Call NotificationForwarder directly to avoid infinite recursion from
        # WebhookForwarder's super(self.__class__, self) pattern when subclassed.
        NotificationForwarder.__init__(self, opts)
        # Webhook attribute defaults
        setattr(self, "url", getattr(self, "url", "http://localhost:12345"))
        setattr(self, "username", getattr(self, "username", None))
        setattr(self, "password", getattr(self, "password", None))
        setattr(self, "insecure", getattr(self, "insecure", "yes"))
        setattr(self, "headers", getattr(self, "headers", None))
        # OAuth2 attribute defaults
        setattr(self, "token_url", getattr(self, "token_url", None))
        setattr(self, "client_id", getattr(self, "client_id", None))
        setattr(self, "client_secret", getattr(self, "client_secret", None))
        setattr(self, "token_scope", getattr(self, "token_scope", None))
        setattr(self, "token_grant_type", getattr(self, "token_grant_type", "client_credentials"))
        setattr(self, "token_expiry_buffer", int(getattr(self, "token_expiry_buffer", 30)))

    def _token_cache_path(self):
        return os.path.join(
            os.environ["OMD_ROOT"], "var", "tmp",
            "notificationforwarder_{}_oauth2token.json".format(self.forwarder_name),
        )

    def acquire_token(self):
        cache_path = self._token_cache_path()
        lock_path = cache_path + ".lock"

        with open(lock_path, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                if os.path.exists(cache_path):
                    with open(cache_path) as f:
                        cached = json.load(f)
                    if time.time() < cached.get("expires_at", 0) - self.token_expiry_buffer:
                        logger.debug("oauth2: using cached token")
                        return cached["access_token"]

                logger.debug("oauth2: acquiring new token from {}".format(self.token_url))
                data = {
                    "grant_type": self.token_grant_type,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                }
                if self.token_scope:
                    data["scope"] = self.token_scope

                resp = requests.post(
                    self.token_url,
                    data=data,
                    timeout=10,
                    verify=(self.insecure != "yes"),
                )
                resp.raise_for_status()
                token_data = resp.json()
                token = token_data["access_token"]
                expires_in = int(token_data.get("expires_in", 3600))
                expires_at = time.time() + expires_in

                with open(cache_path, "w") as f:
                    json.dump({"access_token": token, "expires_at": expires_at}, f)

                logger.debug("oauth2: token acquired, valid for {}s".format(expires_in))
                return token
            except Exception as e:
                logger.critical("oauth2: token acquisition failed: {}".format(e))
                raise
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)

    def submit_one(self, event):
        # Sync logger into the webhook module so WebhookForwarder.submit_one can use it.
        _webhook_module.logger = logger
        try:
            token = self.acquire_token()
        except Exception:
            return False
        hdrs = event.forwarderopts.get("headers") or {}
        if isinstance(hdrs, str):
            hdrs = json.loads(hdrs)
        hdrs["Authorization"] = "Bearer {}".format(token)
        event.forwarderopts["headers"] = hdrs
        return super().submit_one(event)
