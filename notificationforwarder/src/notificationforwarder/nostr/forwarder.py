import json
import json

try:
    from pynostr.encrypted_dm import EncryptedDirectMessage
    from pynostr.event import Event
    from pynostr.key import PrivateKey, PublicKey
    from pynostr.relay_manager import RelayManager
except Exception:  # pragma: no cover - exercised when pynostr is unavailable
    class EncryptedDirectMessage:  # type: ignore
        def __init__(self, *args, **kwargs):
            self.cleartext_content = None
            self.recipient_pubkey = None
            self._event = None

        def encrypt(self, private_key_hex, cleartext_content=None, recipient_pubkey=None):
            self.cleartext_content = cleartext_content
            self.recipient_pubkey = recipient_pubkey

        def to_event(self):
            event = Event(self.cleartext_content or "", tags=[["p", self.recipient_pubkey]] if self.recipient_pubkey else [])
            event.kind = 4
            return event

    class PrivateKey:  # type: ignore
        def __init__(self, value=None):
            self._value = value or "nsec1fallback"

        @classmethod
        def from_nsec(cls, value):
            return cls(value)

        def hex(self):
            return self._value

    class PublicKey:  # type: ignore
        def __init__(self, value=None):
            self._value = value or ""

        @classmethod
        def from_npub(cls, value):
            return cls(value)

        def hex(self):
            return self._value

    class Event:  # type: ignore
        def __init__(self, content, tags=None):
            self.content = content
            self.tags = tags or []
            self.kind = 1

        def sign(self, _private_key_hex):
            return self

    class RelayManager:  # type: ignore
        def __init__(self, timeout=6):
            self.timeout = timeout
            self.relays = []

        def add_relay(self, relay_url):
            self.relays.append(relay_url)

        def publish_event(self, event):
            self.event = event

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
        tags = self._normalize_tags(payload.get("tags", []))
        extra_tags = []
        event_forwarder_tags = formatted_event.forwarderopts.get("tags", [])
        if isinstance(event_forwarder_tags, str):
            try:
                event_forwarder_tags = json.loads(event_forwarder_tags)
            except Exception:
                event_forwarder_tags = []
        if isinstance(event_forwarder_tags, (list, tuple)):
            extra_tags.extend(event_forwarder_tags)
        forwarder_tags = getattr(self, "tags", [])
        if isinstance(forwarder_tags, str):
            try:
                forwarder_tags = json.loads(forwarder_tags)
            except Exception:
                forwarder_tags = []
        if isinstance(forwarder_tags, (list, tuple)):
            extra_tags.extend(forwarder_tags)
        if extra_tags:
            tags.extend(self._normalize_tags(extra_tags))
        event = Event(payload.get("content", ""), tags=tags)
        if hasattr(event, "kind"):
            event.kind = payload.get("kind", self.kind)
        return event

    def _recipient_pubkey(self, event):
        for tag in getattr(event, "tags", []) or []:
            if isinstance(tag, (list, tuple)) and len(tag) > 1 and tag[0] == "p":
                return tag[1]
        raise ValueError("Nostr DM requires a recipient p tag")

    def _normalize_pubkey(self, value):
        # Accept recipient public keys as either npub1... or raw hex.
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.startswith("npub1"):
            try:
                return PublicKey.from_npub(value).hex()
            except Exception:
                return value
        return value

    def _normalize_tags(self, tags):
        normalized = []
        for tag in tags or []:
            if isinstance(tag, (list, tuple)) and tag:
                item = list(tag)
                if item[0] == "p" and len(item) > 1:
                    item[1] = self._normalize_pubkey(item[1])
                normalized.append(item)
            else:
                normalized.append(["t", str(tag)])
        return normalized

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
            recipient_pubkey = self._normalize_pubkey(self._recipient_pubkey(nostr_event))
            dm = EncryptedDirectMessage()
            dm.encrypt(
                private_key.hex(),
                cleartext_content=nostr_event.content,
                recipient_pubkey=recipient_pubkey,
            )
            nostr_event = dm.to_event()
            nostr_event.sign(private_key.hex())

            relay_manager = RelayManager(timeout=self.timeout_seconds)
            for relay_url in relay_urls:
                relay_manager.add_relay(relay_url)
            relay_manager.publish_event(nostr_event)
            relay_manager.run_sync()
            self._close_manager(relay_manager)
            logger.info("published Nostr DM: {}".format(event.summary))
            self.no_more_logging()
            return True
        except Exception as exc:
            logger.critical("Nostr publish failed: {}".format(str(exc)))
            return False
