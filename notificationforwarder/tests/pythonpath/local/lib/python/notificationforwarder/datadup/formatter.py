from notificationforwarder.baseclass import NotificationFormatter

class DatadupFormatter(NotificationFormatter):
    def format_event(self, event):
        """
        Formats a single event.
        """
        # This part is similar to datapost/formatter.py
        event.payload = {
            "source": event.eventopts["source"],
            "action": event.eventopts["action"],
            "site": event.eventopts["site"],
            "split_id": event.eventopts["split_id"], # Add the split_id
        }
        event.summary = f"split event {event.eventopts['split_id']}"

    def split_events(self, raw_event):
        """
        Splits one incoming raw_event into two.
        """
        event1 = raw_event.copy()
        event1["split_id"] = 1

        event2 = raw_event.copy()
        event2["split_id"] = 2

        return [event1, event2]
