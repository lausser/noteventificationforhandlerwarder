from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent


class Split1Formatter(NotificationFormatter):

    def __init__(self):
        pass

    def format_event(self, raw_event):
        logger.info("formatter "+self.__module_file__)
        event = FormattedEvent()
        event.payload = str(raw_event)
        event.summary = "_".join(["{}={}".format(k, raw_event) for k in raw_event])
        return event
