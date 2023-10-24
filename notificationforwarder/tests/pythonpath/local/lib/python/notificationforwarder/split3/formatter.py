from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent


class Split3Formatter(NotificationFormatter):

    def format_event(self, event):
        logger.info("formatter "+self.__module_file__)
        logger.info("i bims dem 3 formanger vong dem Klass {}".format(self.__class__.__name__))
        event.payload = str(event.eventopts)
        event.summary = "_".join(["{}={}".format(k, event.eventopts[k]) for k in event.eventopts])
