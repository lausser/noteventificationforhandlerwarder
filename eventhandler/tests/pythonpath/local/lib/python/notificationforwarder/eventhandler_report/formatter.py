import time
import os
from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class EventhandlerReportFormatter(NotificationFormatter):

    def format_event(self, event):
        json_payload = {
            'timestamp': time.time(),
        }
        json_payload['description'] = event.eventopts['description']
        if 'signature' in event.eventopts:
            json_payload['signature'] = event.eventopts['signature']
        event.payload = json_payload
        # ! event.eventopts["eventhandler_success"] is a string !
        # all eventopts are cast to strings, so "True" or "False"
        event.summary = "eventhandler for {}/{} {} (signature={})".format(event.eventopts["HOSTNAME"], event.eventopts["SERVICEDESC"], "succeeded" if event.eventopts["eventhandler_success"] == "True" else "failed", event.eventopts["signature"])
