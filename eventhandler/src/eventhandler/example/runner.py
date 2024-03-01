from eventhandler.baseclass import EventhandlerRunner

class ExampleRunner(EventhandlerRunner):

    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "username", getattr(self, "username", "guest"))

    def run(self):
        pass
