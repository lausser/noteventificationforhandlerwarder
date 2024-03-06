from eventhandler.baseclass import EventhandlerDecider


class OmdSiteSelfHealDecider(EventhandlerDecider):

    def decide_and_prepare(self, event):
        if event.eventopts["HOSTDOWNTIME"] or event.eventopts["SERVICEDOWNTIME"]:
            event.summary = "{} / {} is in a downtime".format(event.eventopts["SERVICEDESC"], event.eventopts["HOSTNAME"])
            event.discard(silently=False)
        elif event.eventopts["SERVICESTATE"] == "OK":
            event.summary = "{} / {} has recovered".format(event.eventopts["SERVICEDESC"], event.eventopts["HOSTNAME"])
            event.discard(silently=False)
        elif event.eventopts["SERVICEATTEMPT"] == 1:
            event.summary = "restarting {} / {}".format(event.eventopts["SERVICEDESC"], event.eventopts["HOSTNAME"])
            event.payload = {
                'user': event.eventopts["site_name"],
                'command': "local/lib/nagios/plugins/check_omd --heal",
            }
        elif event.eventopts["SERVICEATTEMPT"] == 2:
            event.summary = "restart of {} / {} did not help".format(event.eventopts["SERVICEDESC"], event.eventopts["HOSTNAME"])
            event.discard(silently=False)
        else:
            event.summary = "unhandled state {}".format(event.eventopts)
            event.discard(silently=False)

