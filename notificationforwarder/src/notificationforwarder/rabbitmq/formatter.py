import time
from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class RabbitmqFormatter(NotificationFormatter):

    def format_event(self, event):
        json_payload = {
            'platform': 'Naemon',
            'host_name': event.eventopts["HOSTNAME"],
            'notification_type': event.eventopts["NOTIFICATIONTYPE"],
        }
        if "extra_payload_attributes" in event.eventopts:
            kv_list = [kv.strip() for kv in event.eventopts["extra_payload_attributes"].split(",")]
            for key, value in [kv.strip().split("=") for kv in event.eventopts["extra_payload_attributes"].split(",")]:
                json_payload[key] = value
        if "SERVICEDESC" in event.eventopts:
            json_payload['service_description'] = event.eventopts['SERVICEDESC']
            json_payload['state'] = event.eventopts["SERVICESTATE"]
            json_payload['output'] = event.eventopts["SERVICEOUTPUT"]
        else:
            json_payload['state'] = event.eventopts["HOSTSTATE"]
            json_payload['output'] = event.eventopts["HOSTOUTPUT"]
        event.payload = [json_payload]
        event.summary = str(json_payload)
