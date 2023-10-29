from notificationforwarder.baseclass import NotificationFormatter

class VongFormatter(NotificationFormatter):

    def format_event(self, event):
        json_payload = {
            'greeting': 'Halo i bims 1 eveng vong Naemon her',
            'host_name': event.eventopts["HOSTNAME"],
        }
        if "SERVICEDESC" in event.eventopts:
            json_payload['service_description'] = event.eventopts['SERVICEDESC']
            if event.eventopts["SERVICESTATE"] == "WARNING":
                json_payload['output'] = "dem {} vong {} is schlecht".format(event.eventopts['SERVICEDESC'], event.eventopts['HOSTNAME'])
            elif event.eventopts["SERVICESTATE"] == "CRITICAL":
                json_payload['output'] = "dem {} vong {} is vol kaputt".format(event.eventopts['SERVICEDESC'], event.eventopts['HOSTNAME'])
            else:
                json_payload['output'] = "i bim mit dem Serviz {} vong {} voll zufriedn".format(event.eventopts['SERVICEDESC'], event.eventopts['HOSTNAME'])
        else:
            if event.eventopts["HOSTSTATE"] == "DOWN":
                json_payload['output'] = "dem {} is vol kaputt".format(event.eventopts["HOSTNAME"])
            else:
                json_payload['output'] = "dem {} is 1 host mid Niceigkeit".format(event.eventopts["HOSTNAME"])

        event.payload = json_payload
        event.summary = "i hab dem post gepost"

