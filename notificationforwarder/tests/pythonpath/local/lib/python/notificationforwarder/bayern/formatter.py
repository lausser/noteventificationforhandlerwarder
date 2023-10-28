import time
from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class BayernFormatter(NotificationFormatter):

    def format_event(self, event):
        json_payload = {
            'formatter': 'bayern',
            'da_host': event.eventopts["HOSTNAME"],
            'da_typ': event.eventopts["NOTIFICATIONTYPE"],
        }
        event.payload = json_payload
        event.summary = "des glump {} is hi".format(json_payload["da_host"])
