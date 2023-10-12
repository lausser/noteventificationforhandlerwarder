from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class SyslogFormatter(NotificationFormatter):

    def format_event(self, raw_event):
        event = FormattedEvent()
        if "SERVICEDESC" in raw_event:
            event.set_payload("host: {}, service: {}, state: {}, output: {}".format(raw_event["HOSTNAME"], raw_event["SERVICEDESC"], raw_event["SERVICESTATE"], raw_event["SERVICEOUTPUT"]))
            event.set_summary("host: {}, service: {}, state: {}".format(raw_event["HOSTNAME"], raw_event["SERVICEDESC"], raw_event["SERVICESTATE"]))
        else:
            event.set_payload("host: {}, state: {}, output: {}".format(raw_event["HOSTNAME"], raw_event["HOSTSTATE"], raw_event["HOSTOUTPUT"]))
            event.set_summary("host: {}, state: {}".format(raw_event["HOSTNAME"], raw_event["HOSTSTATE"]))
        return event

