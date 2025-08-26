from notificationforwarder.baseclass import NotificationFormatter

class DatapostFormatter(NotificationFormatter):
    def format_event(self, event):
        """
        Creates a dictionary payload from eventopts.
        """
        event.payload = {
            "source": event.eventopts["source"],
            "action": event.eventopts["action"],
            "site": event.eventopts["site"],
        }
        event.summary = "dict payload"