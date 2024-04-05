import time
from eventhandler.baseclass import EventhandlerRunner

class ExampleRunner(EventhandlerRunner):

    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "echofile", getattr(self, "echofile", "/tmp/echo"))
        setattr(self, "delay", getattr(self, "delay", None))

    def run(self, event):
        if self.delay:
            time.sleep(self.delay)
        return "echo '{}' > {}".format(event.payload["content"], self.echofile)

