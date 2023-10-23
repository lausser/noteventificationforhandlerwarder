from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent


class Split4Formatter(NotificationFormatter):

    def format_event(self, event):
        logger.info("formatter "+self.__module_file__)
        event.payload = str(event.eventopts)
        event.summary = "split4_"+("_".join(["{}={}".format(k, event.eventopts[k]) for k in event.eventopts]))
        if "signature" in event.eventopts:
            event.summary = "split4_"+event.eventopts["signature"]+"_"+event.summary
