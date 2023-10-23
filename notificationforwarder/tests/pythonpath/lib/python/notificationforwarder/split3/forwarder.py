from notificationforwarder.baseclass import NotificationForwarder, NotificationFormatter, timeout


class Split3Forwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        self.url = "https://split1.com"

    @timeout(30)
    def submit(self, event):
        logger.info("forwarder "+self.__module_file__)
        return True

