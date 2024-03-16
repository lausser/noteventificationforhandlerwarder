import os
from eventhandler.baseclass import EventhandlerRunner

class NscWebRunner(EventhandlerRunner):

    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "hostname", getattr(self, "hostname", "localhost"))
        setattr(self, "port", getattr(self, "port", 8443))
        setattr(self, "password", getattr(self, "password", None))
        setattr(self, "command", getattr(self, "command", "check_uptime"))
        setattr(self, "arguments", getattr(self, "arguments", None))

    def run(self, event):
        cmd = "{}/lib/nagios/plugins/check_nsc_web -k -u https://{}:{} -p '{}' -t 180".format(os.environ["OMD_ROOT"], self.hostname, self.port, self.password)
        if self.arguments:
            cmd += " {} '{}'".format(self.command, self.arguments)
        else:
            cmd += " {}".format(self.command)
        return cmd
