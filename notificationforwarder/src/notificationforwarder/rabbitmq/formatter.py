import time
import os
from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class RabbitmqFormatter(NotificationFormatter):

    def format_event(self, raw_event):
        event = FormattedEvent()
        json_payload = {
            'platform': 'Naemon',
            'host_name': raw_event["HOSTNAME"],
            'notification_type': raw_event["NOTIFICATIONTYPE"],
        }
        if "extra_payload_attributes" in raw_event:
            kv_list = [kv.strip() for kv in raw_event["extra_payload_attributes"].split(",")]
            for key, value in [kv.strip().split("=") for kv in raw_event["extra_payload_attributes"].split(",")]:
                json_payload[key] = value
        if "SERVICEDESC" in raw_event:
            json_payload['service_description'] = raw_event['SERVICEDESC']
            json_payload['state'] = raw_event["SERVICESTATE"]
            json_payload['output'] = raw_event["SERVICEOUTPUT"]
        else:
            json_payload['state'] = raw_event["HOSTSTATE"]
            json_payload['output'] = raw_event["HOSTOUTPUT"]
        event.set_payload([json_payload])
        event.set_summary(str(json_payload))
        return event

