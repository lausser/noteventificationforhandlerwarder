import time
import os
from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class ExampleFormatter(NotificationFormatter):

    def format_event(self, event):
        json_payload = {
            'timestamp': time.time(),
        }
        json_payload['description'] = event.eventopts['description']
        if 'signature' in event.eventopts:
            json_payload['signature'] = event.eventopts['signature']
        event.payload = json_payload
        event.summary = "sum: "+json_payload['description']

