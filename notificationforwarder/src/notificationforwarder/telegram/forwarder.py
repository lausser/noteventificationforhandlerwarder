import requests
import urllib.parse
from notificationforwarder.baseclass import NotificationForwarder, timeout

class TelegramForwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "bot_token", getattr(self, "bot_token", None))
        setattr(self, "chat_id", getattr(self, "hat_id", None))

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
        # self.bot_token
        # self.chat_id
        try:
            request_params = {}
            request_params["text"] = urllib.parse.quote(event.payload)
            request_params["parse_mode"] = "MarkdownV2"
            request_params["chat_id"] = self.chat_id
            response = requests.get("https://api.telegram.org/bot{}/sendMessage".format(self.bot_token), params=request_parms)
            if response.status_code == requests.codes.ok:
                logger.info("success: {} result is {}, request was {}".format(event.summary, response.text, request_params))
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

