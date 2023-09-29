import time
import os
from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class RabbitmqFormatter(NotificationFormatter):

    def format_event(self, raw_event):
        event = FormattedEvent()
        print("formatter ", event.__dict__)
        print("formatter ", self.__dict__)
        print("formatter ", raw_event)
        json_payload = {
            'omd_site': os.environ["OMD_SITE"],
            'platform': 'Naemon',
            'host_name': raw_event["HOSTNAME"],
            'notification_type': raw_event["NOTIFICATIONTYPE"],
            'timestamp': time.time(),
        }
        if "SERVICEDESC" in raw_event:
            json_payload['service_description'] = raw_event['service_description']
            json_payload['state'] = raw_event["state"]
            json_payload['output'] = raw_event["output"]
        else:
            json_payload['state'] = raw_event["state"]
            json_payload['output'] = raw_event["output"]
        event.set_payload(json_payload)
        event.set_summary(json_payload)
        return event

