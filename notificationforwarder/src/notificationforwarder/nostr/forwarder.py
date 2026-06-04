import json

from pynostr.encrypted_dm import EncryptedDirectMessage
from pynostr.event import Event
from pynostr.key import PrivateKey, PublicKey
import pynostr.relay as relay_mod
from pynostr.relay_manager import RelayManager

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

            orig_websocket_connect = relay_mod.websocket_connect
            relay_mod.websocket_connect = lambda *a, **k: orig_websocket_connect(
                *a, **{**k, "ping_timeout": min(k.get("ping_timeout", 0), k.get("ping_interval", 0))}
            )

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
