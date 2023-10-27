import json
import requests
import os
from notificationforwarder.baseclass import NotificationForwarder, timeout

class WebhookForwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "url", getattr(self, "url", "http://localhost:12345"))
        setattr(self, "username", getattr(self, "username", None))
        setattr(self, "password", getattr(self, "password", None))
        setattr(self, "headers", getattr(self, "headers", None))

    @timeout(30)
    def submit(self, event):
        if type(event) == list:
            for one_event in event:
                if not self.submit_one(one_event):
                    return False
            return True
        else:
            success = self.submit_one(event)
            if event.is_heartbeat: # should not be spooled and re-sent
                return True
            else:
                return success

    def submit_one(self, event):
        # event.payload = the json payload
        # event.summary = for the log line
        # event.fowarderopts["headers"] =
        # self.username
        # self.password
        # self.headers = 
        try:
            request_params = {}
            request_params["json"] = event.payload
            if self.username and self.password:
                request_params["auth"] = requests.auth.HTTPBasicAuth(self.usename, self.passwod)
            if self.headers:
                if isinstance(headers, str):
                    # can be --eventopts='{"my-key": "my-value"}'
                    headers = json.loads(headers)
                request_params["headers"] = headers
            if hasattr(event, "forwarderopts") and "headers" in event.fowarderopts:
                if "headers" not in request_params:
                    request_params["headers"] = {}
                request_params["headers"].update(event.fowarderopts["headers"])

            response = requests.post(self.url, **request_params)
            if response.status_code == requests.codes.ok:
                logger.info("success: {} result is {}, request was {}".format(event.summary, response.text, event.payload))
                return True
            elif response.status_code in [requests.codes.timeout, requests.codes.gateway_timeout]:
                logger.critical("POST timeout "+str(response.status_code)+" "+response.text)
                return False
            elif response.status_code == requests.codes.internal_server_error and "Connection timed out" in response.reason:
                logger.critical("POST timeout "+str(response.status_code)+" "+response.text)
                return False

            else:
                logger.critical("POST failed "+str(response.status_code)+" "+response.text)
                return False
        except Exception as e:
            logger.critical("POST had an exception: {}".format(str(e)))
            return False

