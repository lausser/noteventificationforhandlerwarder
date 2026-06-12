import json

from notificationforwarder.baseclass import NotificationFormatter


class NostrFormatter(NotificationFormatter):
    def _pick(self, event, *names, default=""):
        for name in names:
            value = event.eventopts.get(name)
            if value not in (None, ""):
                return value
        return default

    def _build_tags(self, host, service, state, extra_tags=None):
        tags = [["t", "monitoring"]]
        if host:
            tags.append(["host", host])
        if service:
            tags.append(["service", service])
        if state:
            tags.append(["state", state])
        if isinstance(extra_tags, str):
            try:
                extra_tags = json.loads(extra_tags)
            except Exception:
                extra_tags = []
        for tag in extra_tags or []:
            if isinstance(tag, (list, tuple)) and tag:
                tags.append(list(tag))
        return tags

    def format_event(self, event):
        host = self._pick(event, "HOSTNAME", "HOST", "HOSTNAME_SHORT", "HOSTNAME_FULL")
        service = self._pick(event, "SERVICEDESC", "SERVICE", default="")
        state = self._pick(event, "SERVICESTATE", "HOSTSTATE", "STATE", default="")
        output = self._pick(event, "SERVICEOUTPUT", "HOSTOUTPUT", "OUTPUT", default="")

        lines = [
            f"Host: {host}",
            f"Service: {service or '-'}",
            f"State: {state or '-'}",
            f"Output: {output or '-'}",
        ]
        content = "\n".join(lines)
        event.payload = {
            "content": content,
            "tags": self._build_tags(
                host,
                service,
                state,
                event.forwarderopts.get("tags"),
            ),
        }
        event.summary = f"{host or 'unknown'}/{service or '-'}: {state or '-'}"
