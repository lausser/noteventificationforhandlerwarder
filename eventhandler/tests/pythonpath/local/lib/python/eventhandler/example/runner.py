import time
from eventhandler.baseclass import EventhandlerRunner

class ExampleRunner(EventhandlerRunner):

    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "echofile", getattr(self, "echofile", "/tmp/echo"))

    def run(self, event):
        if "delay" in event.payload:
            time.sleep(event.payload["delay"])
        return "echo '{}' > {}".format(event.payload["content"], self.echofile)

