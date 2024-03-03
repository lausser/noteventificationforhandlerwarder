from eventhandler.baseclass import EventhandlerDecider


class ExampleDecider(EventhandlerDecider):

    def decide_and_prepare(self, event):
        event.discard()
        event.summary = "halo i bims 1 alarm vong naemon her und i schmeis mi weg"
        event.payload = {
            "cmd": "echo",
            "parameters": "halo i bims 1 alarm vong naemon her",
        }
