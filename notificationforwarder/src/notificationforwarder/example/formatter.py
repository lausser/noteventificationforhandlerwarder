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
        event.set_payload(json_payload)
        event.set_summary("this is an example")
        return event

