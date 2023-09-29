from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class SyslogFormatter(NotificationFormatter):

    def format_event(self, raw_event):
        if "service_description" in raw_event:
            return("host: {}, service: {}, state: {}, output: {}".format(raw_event["host_name"], raw_event["service_description"], raw_event["state"], raw_event["output"]))
        else:
            return("host: {}, state: {}, output: {}".format(raw_event["host_name"], raw_event["state"], raw_event["output"]))

