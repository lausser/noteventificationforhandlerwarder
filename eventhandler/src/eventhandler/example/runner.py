import subprocess
from eventhandler.baseclass import EventhandlerRunner

class ExampleRunner(EventhandlerRunner):

    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "echofile", getattr(self, "echofile", "/tmp/echo"))

    def run(self, event):
        cmd = "echo '{}' > {}".format(event.payload["content"], self.echofile)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

