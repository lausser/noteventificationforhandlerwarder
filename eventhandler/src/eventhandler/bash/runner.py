from eventhandler.baseclass import EventhandlerRunner

class BashRunner(EventhandlerRunner):

    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "command", getattr(self, "command", "exit 0"))


    def run(self, event):
        cmd = "bash -c '{}'".format(self.command)
        return cmd
