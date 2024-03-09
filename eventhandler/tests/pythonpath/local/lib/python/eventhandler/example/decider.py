from eventhandler.baseclass import EventhandlerDecider


class ExampleDecider(EventhandlerDecider):

    def decide_and_prepare(self, event):
        if "discard" in event.eventopts:
            event.discard(silently=event.eventopts["discard"])
            event.summary = "halo i bims 1 alarm vong naemon her und i schmeis mi weg"
        else:
            event.summary = event.eventopts.get("summary", None)
        event.payload = {
            "content": event.eventopts["content"],
        }
        if "delay" in event.eventopts:
            event.payload["delay"] = event.eventopts["delay"]
