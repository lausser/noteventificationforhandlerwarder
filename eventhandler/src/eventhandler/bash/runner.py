from eventhandler.baseclass import EventhandlerRunner

class BashRunner(EventhandlerRunner):

    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)

    def run(self, event):
        cmd = "bash -c '{}'".format(event.payload["command"])
        return cmd
