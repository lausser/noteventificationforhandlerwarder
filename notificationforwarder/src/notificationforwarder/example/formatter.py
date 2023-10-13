import time
import os
from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class ExampleFormatter(NotificationFormatter):

    def format_event(self, raw_event):
        event = FormattedEvent()
        json_payload = {
            'timestamp': time.time(),
        }
        json_payload['description'] = raw_event['description']
        if 'signature' in raw_event:
            json_payload['signature'] = raw_event['signature']
        event.set_payload(json_payload)
        event.set_summary("sum: "+json_payload['description'])
        return event

