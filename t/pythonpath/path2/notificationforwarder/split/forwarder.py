import json
import requests
import os
from notificationforwarder.baseclass import NotificationForwarder, NotificationFormatter, timeout
print("Split.__class__")


class Split(NotificationForwarder):
    def __init__(self, opts):
        print("Split.__init__1")
        super(self.__class__, self).__init__(opts)
        print("Split.__init__2")
        self.url = "https://split.com"

    @timeout(30)
    def submit(self, payload):
        print("forward {}".format(payload.__dict__))
        return True

