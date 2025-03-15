import json
import time
import logging
from notificationforwarder.baseclass import NotificationForwarder, NotificationFormatter, timeout


class ExampleForwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "username", getattr(self, "username", "guest"))
        setattr(self, "delay", int(getattr(self, "delay", 0)))
        setattr(self, "fail", getattr(self, "fail", None))
        setattr(self, "signaturefile", getattr(self, "signaturefile", "/tmp/notificationforwarder_example.txt"))
        setattr(self, "file", getattr(self, "file", "/tmp/notificationforwarder_example_api.txt"))
        self.parameter = "sample"

    @timeout(2, error_message="submit ran into a timeout")
    def submit(self, event):
        time.sleep(self.delay)
        if True: # for example if self.connect()
            try:
                logger.info("{} submits {}".format(self.username, event.__dict__))
                if self.fail:
                    logger.critical("sample api does not accept the payload")
                    return False
                elif "signature" in event.payload:
                    with open(self.signaturefile, "a") as f:
                        print(event.payload["signature"], file=f)
                    with open(self.file, "a") as f:
                        print(str(event.payload), file=f)
                    return True
                else:
                    with open(self.file, "a") as f:
                        print(str(event.payload), file=f)
                    return True
            except Exception as e:
                logger.critical("sample api post had an exception: {} with payload {}".format(str(e), str(event.payload)))
                return False
        else:
           logger.critical("could not connect to the ticket system")
           return False

    def probe(self):
        return True
