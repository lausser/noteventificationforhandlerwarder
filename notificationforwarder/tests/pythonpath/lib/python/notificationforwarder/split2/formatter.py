from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent


class Split2Formatter(NotificationFormatter):

    def format_event(self, event):
        logger.info("formatter "+self.__module_file__)
        event.payload = str(event.eventopts)
        event.summary = "_".join(["{}={}".format(k, event.eventopts[k]) for k in event.eventopts])
