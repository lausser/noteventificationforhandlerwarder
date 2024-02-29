import notificationforwarder
from notificationforwarder.baseclass import NotificationForwarder, NotificationFormatter, timeout
from notificationforwarder.split1 import Split1Forwarder


class Split4Forwarder(notificationforwarder.split1.Split1Forwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        self.url2 = "https://split4.com"

