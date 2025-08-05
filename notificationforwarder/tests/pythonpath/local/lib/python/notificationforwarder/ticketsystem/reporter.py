import time
import os
from notificationforwarder.baseclass import NotificationReporter, timeout

class TicketsystemReporter(NotificationReporter):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "api", getattr(self, "api", "cmd"))
        setattr(self, "command_file", getattr(self, "command_file", None))
        setattr(self, "forwarder_report_payload", getattr(self, "forwarder_report_payload", None))


    def report_event(self, event):
        if not "CONTACTNAME" in event.eventopts:
            event.eventopts["CONTACTNAME"] = "GLOBAL"
        if not "NOTIFICATIONCOMMAND" in event.eventopts:
            event.eventopts["NOTIFICATIONCOMMAND"] = "global_{}_notification_handler".format("service" if "SERVICEDESC" in event.eventopts else "host")
        if "SERVICEDESC" in event.eventopts:
            text = "SERVICE NOTIFICATION: {};{};{};{};{};{}".format(event.eventopts["CONTACTNAME"], event.eventopts["HOSTNAME"], event.eventopts["SERVICEDESC"], event.eventopts["NOTIFICATIONCOMMAND"], event.eventopts["SERVICESTATE"], event.eventopts["SERVICEOUTPUT"])
        else:
            text = "HOST NOTIFICATION: {};{};{};{};{}".format(event.eventopts["CONTACTNAME"], event.eventopts["HOSTNAME"], event.eventopts["NOTIFICATIONCOMMAND"], event.eventopts["HOSTSTATE"], event.eventopts["HOSTOUTPUT"])
        if not event.eventopts["forwarder_success"]:
            text += " (could not be forwarded to {})".format(event.eventopts["forwarder_name"])
        if "forwarder_report_payload" in event.eventopts:
            text += f" created {event.eventopts['forwarder_report_payload']['number']}/{event.eventopts['forwarder_report_payload']['message']}"
        if self.forwarder_report_payload:
            text += " "+self.forwarder_report_payload["number"]
        if self.api == "cmd":
            command_file = None
            if self.command_file:
                command_file = self.command_file
            else:
                nagios_cfg = os.environ["OMD_ROOT"]+"/tmp/naemon/naemon.cfg"
                if os.path.exists(nagios_cfg):
                    with open(nagios_cfg, 'r') as file:
                        for line in file:
                            if line.startswith('command_file='):
                                command_file = line.split('=', 1)[1].strip()
            if command_file:
                with open(command_file, "a") as cmd:
                    cmd.write("[{}] LOG;{}\n".format(int(time.time()), text))
            else:
                pass

        return

