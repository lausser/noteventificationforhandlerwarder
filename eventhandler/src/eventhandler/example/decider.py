from eventhandler.baseclass import EventhandlerDecider


class ExampleDecider(EventhandlerDecider):

    def decide_and_prepare(self, event):
        event.discard()
        event.summary = "halo i bims 1 alarm vong naemon her und i schmeis mi weg"
        print("============>>>>{}".format(event.__dict__))
        for i in event.eventopts:
            print("{} = {}".format(i, event.eventopts[i]))
        event.payload = {
            "cmd": "echo",
            "parameters": "halo i bims 1 alarm vong naemon her",
            "timestamp": event.eventopts["omd_originating_timestamp"],
        }
