from notificationforwarder.baseclass import NotificationForwarder


class TicketsystemForwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "signature", getattr(self, "signature", None))

    def submit(self, event):
        if not self.signature:
            return {
                "success": False,
                "report_payload": "failed"
            }
        else:
            return {
                "success": True,
                "report_payload": {
                    "number": "INC00000000",
                    "message": self.signature,
                }
            }
