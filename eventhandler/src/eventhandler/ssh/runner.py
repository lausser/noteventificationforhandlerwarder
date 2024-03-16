from eventhandler.baseclass import EventhandlerRunner

class SshRunner(EventhandlerRunner):

    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "username", getattr(self, "username", None))
        setattr(self, "hostname", getattr(self, "hostname", "localhost"))
        setattr(self, "port", getattr(self, "port", None))
        setattr(self, "identity_file", getattr(self, "identity_file", None))
        setattr(self, "command", getattr(self, "command", "exit 0"))

    def run(self, event):
        cmd = "ssh"
        if self.username:
            cmd += f" -l {self.username}"
        if self.port:
            cmd += f" -p {self.port}"
        if self.identity_file:
            cmd += f" -i {self.identity_file}"
        cmd += " {} '{}'".format(self.hostname, self.command)
        return cmd
