from eventhandler.baseclass import EventhandlerDecider


class ExampleDecider(EventhandlerDecider):

    def decide_and_prepare(self, event):
        event.discard()
        print("i decide and prepare based on {}".format(event.__dict__))
        print("i decide and prepare based on {}".format(event.eventopts["description"]))
