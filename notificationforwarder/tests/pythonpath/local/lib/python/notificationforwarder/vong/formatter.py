import time
from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class VongFormatter(NotificationFormatter):

    def format_event(self, event):
        json_payload = {
            'formatter': 'vong',
            'dem_host': event.eventopts["HOSTNAME"],
            'dem_typ': event.eventopts["NOTIFICATIONTYPE"],
        }
        if "dem_is_geheim" in event.eventopts:
            event.forwarderopts["headers"] = '{{"Authorization": "Bearer {}"}}'.format(event.eventopts["dem_is_geheim"])
        event.payload = json_payload
        event.summary = "dem {} is kaputt".format(json_payload["dem_host"])
