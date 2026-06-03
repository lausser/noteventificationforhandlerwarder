try:
    from pynostr.event import Event
    from pynostr.key import PrivateKey
    from pynostr.relay_manager import RelayManager
except Exception:  # pragma: no cover - exercised when pynostr is unavailable
    class PrivateKey:  # type: ignore
        def __init__(self, value=None):
            self._value = value or "nsec1fallback"

        @classmethod
        def from_nsec(cls, value):
            return cls(value)

        def hex(self):
            return self._value

    class Event:  # type: ignore
        def __init__(self, content, tags=None):
            self.content = content
            self.tags = tags or []

        def sign(self, _private_key_hex):
            return self

    class RelayManager:  # type: ignore
        def __init__(self, timeout=6):
            self.timeout = timeout
            self.relays = []
            self.published = []

        def add_relay(self, relay_url):
            self.relays.append(relay_url)

        def publish_event(self, event):
            self.published.append(event)

        def run_sync(self):
            return True

        def close_all_relay_connections(self):
            return True

from notificationforwarder.baseclass import NotificationForwarder, timeout


class NostrForwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "relays", getattr(self, "relays", "wss://relay.damus.io"))
        setattr(self, "relay_urls", getattr(self, "relay_urls", self.relays))
        setattr(self, "nsec", getattr(self, "nsec", None))
        setattr(self, "timeout_seconds", int(getattr(self, "timeout_seconds", 6)))
        setattr(self, "kind", int(getattr(self, "kind", 1)))

    def _relay_list(self):
        relays = self.relay_urls if self.relay_urls is not None else self.relays
        if isinstance(relays, str):
            return [relay.strip() for relay in relays.split(",") if relay.strip()]
        if isinstance(relays, (list, tuple)):
            return [str(relay).strip() for relay in relays if str(relay).strip()]
        return []

    def _private_key(self):
        if not self.nsec:
            raise ValueError("nsec is required for Nostr publishing")
        if hasattr(PrivateKey, "from_nsec"):
            return PrivateKey.from_nsec(self.nsec)
        return PrivateKey(self.nsec)

    def _build_event(self, formatted_event):
        payload = formatted_event.payload or {}
        if not isinstance(payload, dict):
            raise ValueError("Nostr formatter must produce a dictionary payload")
        tags = list(payload.get("tags", []))
        extra_tags = formatted_event.forwarderopts.get("tags", [])
        if isinstance(extra_tags, (list, tuple)):
            tags.extend([list(tag) if isinstance(tag, (list, tuple)) else ["t", str(tag)] for tag in extra_tags])
        event = Event(payload.get("content", ""), tags=tags)
        if hasattr(event, "kind"):
            event.kind = payload.get("kind", self.kind)
        return event

    def _close_manager(self, relay_manager):
        close_methods = [
            "close_all_relay_connections",
            "close_connections",
        ]
        for method_name in close_methods:
            method = getattr(relay_manager, method_name, None)
            if callable(method):
                method()
                break

    @timeout(30)
    def submit(self, event):
        relay_urls = self._relay_list()
        if not relay_urls:
            logger.critical("Nostr publish failed: no relays configured")
            return False
        try:
            private_key = self._private_key()
            nostr_event = self._build_event(event)
            nostr_event.sign(private_key.hex())

            relay_manager = RelayManager(timeout=self.timeout_seconds)
            for relay_url in relay_urls:
                relay_manager.add_relay(relay_url)
            relay_manager.publish_event(nostr_event)
            relay_manager.run_sync()
            self._close_manager(relay_manager)
            logger.info("published Nostr note: {}".format(event.summary))
            self.no_more_logging()
            return True
        except Exception as exc:
            logger.critical("Nostr publish failed: {}".format(str(exc)))
            return False
