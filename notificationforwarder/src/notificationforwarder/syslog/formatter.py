from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent

class SyslogFormatter(NotificationFormatter):

    def format_event(self, raw_event):
        event = FormattedEvent()
        if "service_description" in raw_event:
            event.set_payload("host: {}, service: {}, state: {}, output: {}".format(raw_event["host_name"], raw_event["service_description"], raw_event["state"], raw_event["output"]))
            event.set_summary("host: {}, service: {}, state: {}".format(raw_event["host_name"], raw_event["service_description"], raw_event["state"]))
        else:
            event.set_payload("host: {}, state: {}, output: {}".format(raw_event["host_name"], raw_event["state"], raw_event["output"]))
            event.set_summary("host: {}, state: {}".format(raw_event["host_name"], raw_event["state"]))
        return event
