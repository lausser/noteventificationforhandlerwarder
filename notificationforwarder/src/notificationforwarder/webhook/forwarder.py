import json
import requests
import os
from notificationforwarder.baseclass import NotificationForwarder, timeout


class Servicenow(NotificationForwarder):

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
        # event.meta = 
        # self.basic_auth_user
        # self.basic_auth_pass
        # self.headers = 
        try:
            response = requests.post(self.url, json=event.payload, auth=requests.auth.HTTPBasicAuth(self.basic_auth_user, self.basic_auth_pass))
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

