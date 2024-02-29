from notificationforwarder.baseclass import NotificationFormatter, FormattedEvent


class DiscardFormatter(NotificationFormatter):

    def format_event(self, event):
        event.payload = str(event.eventopts)
        if event.eventopts["was_i_machn_tu"] == "nix":
            pass
        elif event.eventopts["was_i_machn_tu"] == "dem semf dazugebn":
            event.discard(silently=False)
            event.summary = "dem semf"
            return
        elif event.eventopts["was_i_machn_tu"] == "dem automatischn semf dazugebn":
            event.discard(silently=False)
        elif event.eventopts["was_i_machn_tu"] == "dem maul haltn":
            event.discard()
            pass
        event.summary = "_".join(["{}={}".format(k, event.eventopts[k]) for k in event.eventopts])
