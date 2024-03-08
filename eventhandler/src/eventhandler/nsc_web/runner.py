import os
from eventhandler.baseclass import EventhandlerRunner

class NscWebRunner(EventhandlerRunner):

    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "hostname", getattr(self, "hostname", "localhost"))
        setattr(self, "port", getattr(self, "port", 8443))
        setattr(self, "password", getattr(self, "password", None))

    def run(self, event):
        cmd = "{}/lib/nagios/plugins/check_nsc_web -k -u https://{}:{} -p '{}' -t 180".format(os.environ["OMD_ROOT"], self.hostname, self.port, self.password)
        if "arguments" in event.payload:
            cmd += " {} '{}'".format(event.payload["command"], event.payload["arguments"])
        else:
            cmd += " {}".format(event.payload["command"])
        return cmd
