from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent


class SplitFormatter(NotificationFormatter):

    def __init__(self):
        pass

    def format_event(self, raw_event):
        print("in split.format_event")
        event = FormattedEvent()
        event.payload = str(raw_event)
        event.summary = "_".join(["{}={}".format(k, raw_event) for k in raw_event])
        return event
