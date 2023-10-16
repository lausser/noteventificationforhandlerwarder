from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class SyslogFormatter(NotificationFormatter):

    def format_event(self, event):
        if "SERVICEDESC" in event.eventopts:
            event.payload = "host: {}, service: {}, state: {}, output: {}".format(event.eventopts["HOSTNAME"], event.eventopts["SERVICEDESC"], event.eventopts["SERVICESTATE"], event.eventopts["SERVICEOUTPUT"])
            event.summary = "host: {}, service: {}, state: {}".format(event.eventopts["HOSTNAME"], event.eventopts["SERVICEDESC"], event.eventopts["SERVICESTATE"])
        else:
            event.payload = "host: {}, state: {}, output: {}".format(event.eventopts["HOSTNAME"], event.eventopts["HOSTSTATE"], event.eventopts["HOSTOUTPUT"])
            event.summary = "host: {}, state: {}".format(event.eventopts["HOSTNAME"], event.eventopts["HOSTSTATE"])

