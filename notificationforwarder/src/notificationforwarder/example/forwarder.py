import json
import time
import logging
from notificationforwarder.baseclass import NotificationForwarder, NotificationFormatter, timeout


class Example(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "username", getattr(self, "username", "guest"))
        setattr(self, "delay", int(getattr(self, "delay", 0)))
        setattr(self, "fail", getattr(self, "fail", None))
        self.parameter = "sample"

    @timeout(30)
    def submit(self, payload):
        time.sleep(self.delay)
        if True: # for example if self.connect()
            try:
                logger.info("{} submits {}".format(self.username, payload.__dict__))
                if self.fail:
                    logger.critical("sample api does not accept the payload")
                    return False
                else:
                    return True
            except Exception as e:
                logger.critical("sample api post had an exception: {} with payload {}".format(str(e), str(payload)))
                return False
        else:
           logger.critical("could not connect to the ticket system")
           return False
