import json
import requests
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
import os
from notificationforwarder.baseclass import NotificationForwarder, timeout

class WebhookForwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "url", getattr(self, "url", "http://localhost:12345"))
        setattr(self, "username", getattr(self, "username", None))
        setattr(self, "password", getattr(self, "password", None))
        setattr(self, "insecure", getattr(self, "insecure", "yes"))
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
        # event.forwarderopts["headers"] =
        # self.username
        # self.password
        # self.headers = 
        try:
            request_params = {}
            mode = event.forwarderopts.get("mode", "json")
            if mode == "json":
                request_params["json"] = event.payload
            elif mode == "form":
                if isinstance(event.payload, dict):
                    request_params["data"] = event.payload
                else:
                    request_params["data"] = {"data": event.payload}
            elif mode == "raw":
                if isinstance(event.payload, (dict, list)):
                    request_params["data"] = json.dumps(event.payload)
                else:
                    request_params["data"] = str(event.payload)
            else:
                raise ValueError(f"Unsupported forwarder mode: {mode}")

            if self.username and self.password:
                request_params["auth"] = requests.auth.HTTPBasicAuth(self.username, self.password)
            if self.headers:
                if isinstance(self.headers, str):
                    # can be --eventopts headers='{"my-key": "my-value"}'
                    request_params["headers"] = json.loads(self.headers)
                else:
                    request_params["headers"] = self.headers
            if "url" in event.forwarderopts:
                logger.debug(f"formatter overwrites the url with {event.forwarderopts['url']}")
                self.url = event.forwarderopts["url"]
            if "headers" in event.forwarderopts:
                if isinstance(event.forwarderopts["headers"], str):
                    event.forwarderopts["headers"] = json.loads(event.forwarderopts["headers"])
                if "headers" not in request_params:
                    request_params["headers"] = {}
                request_params["headers"].update(event.forwarderopts["headers"])
            if self.insecure == "yes":
                request_params["verify"] = False

            if "headers" not in request_params:
                request_params["headers"] = {}
            if "content-type" not in [k.lower() for k in request_params["headers"]]:
                if mode == "json":
                    request_params["headers"]["Content-Type"] = "application/json"
                elif mode == "form":
                    request_params["headers"]["Content-Type"] = "application/x-www-form-urlencoded"
                elif mode == "raw":
                    request_params["headers"]["Content-Type"] = "text/xml"

            response = requests.post(self.url, **request_params)
            if response.status_code in [requests.codes.ok, requests.codes.accepted, requests.codes.created]:
                logger.info("success: {} result is {}, request was {}".format(event.summary, response.text, event.payload))
                self.no_more_logging()
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
