import asyncio

try:
    from nostr_sdk import Client, Keys, NostrSigner, PublicKey, RelayUrl, Tag, uniffi_set_event_loop
except ImportError as exc:
    raise ImportError("missing nostr-sdk") from exc

from notificationforwarder.baseclass import NotificationForwarder, timeout


class NostrForwarder(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "relays", getattr(self, "relays", "wss://relay.damus.io"))
        setattr(self, "relay_urls", getattr(self, "relay_urls", self.relays))
        setattr(self, "nsec", getattr(self, "nsec", None))
        setattr(self, "timeout_seconds", int(getattr(self, "timeout_seconds", 6)))

    def _relay_list(self):
        relays = self.relay_urls if self.relay_urls is not None else self.relays
        if isinstance(relays, str):
            return [relay.strip() for relay in relays.split(",") if relay.strip()]
        if isinstance(relays, (list, tuple)):
            return [str(relay).strip() for relay in relays if str(relay).strip()]
        return []

    def _keys(self):
        if not self.nsec:
            raise ValueError("nsec is required for Nostr publishing")
        return Keys.parse(self.nsec)

    def _public_key(self, value):
        if isinstance(value, PublicKey):
            return value
        if not isinstance(value, str):
            raise ValueError("receiver public key must be a string or PublicKey")
        return PublicKey.parse(value)

    def _tags(self, formatted_event):
        tags = []
        payload = formatted_event.payload or {}
        tag_values = payload.get("tags", [])
        if isinstance(tag_values, str):
            import json

            try:
                tag_values = json.loads(tag_values)
            except Exception:
                tag_values = []
        if isinstance(tag_values, (list, tuple)):
            for tag in tag_values:
                if isinstance(tag, (list, tuple)) and tag:
                    tags.append(Tag.parse(list(tag)))
        return tags

    def _configured_tags(self):
        tag_values = getattr(self, "tags", [])
        if isinstance(tag_values, str):
            import json

            try:
                tag_values = json.loads(tag_values)
            except Exception:
                tag_values = []
        return tag_values if isinstance(tag_values, (list, tuple)) else []

    def _nip_mode(self):
        return getattr(self, "nip_mode", "nip04")

    async def _send_private_msg(self, relay_urls, receiver_pubkey, message, tags):
        uniffi_set_event_loop(asyncio.get_running_loop())
        keys = self._keys()
        signer = NostrSigner.keys(keys)
        client = Client(signer)
        relay_urls = [RelayUrl.parse(url) for url in relay_urls]

        for relay_url in relay_urls:
            await client.add_relay(relay_url)

        await client.connect()
        return await client.send_private_msg_to(relay_urls, receiver_pubkey, message, tags)

    async def _send_nip04_dm(self, relay_urls, receiver_pubkey, message):
        uniffi_set_event_loop(asyncio.get_running_loop())
        keys = self._keys()
        signer = NostrSigner.keys(keys)
        client = Client(signer)
        relay_urls = [RelayUrl.parse(url) for url in relay_urls]

        for relay_url in relay_urls:
            await client.add_relay(relay_url)

        await client.connect()
        return await client.send_private_msg_to(relay_urls, receiver_pubkey, message, [])

    @timeout(30)
    def submit(self, event):
        relay_urls = self._relay_list()
        if not relay_urls:
            logger.critical("Nostr publish failed: no relays configured")
            return False

        payload = event.payload or {}
        nip_mode = self._nip_mode()
        tags = self._configured_tags() or payload.get("tags", [])
        recipient_pubkey = None
        for tag in tags or []:
            if isinstance(tag, (list, tuple)) and len(tag) > 1 and tag[0] == "p":
                recipient_pubkey = self._public_key(tag[1])
                break
        if recipient_pubkey is None:
            raise ValueError("Nostr DM requires a recipient p tag")

        try:
            message = payload.get("content", event.summary or str(payload))
            nip_mode = self._nip_mode()
            logger.debug("Nostr NIP mode: {}".format(nip_mode))
            if nip_mode == "nip17":
                asyncio.run(self._send_private_msg(relay_urls, recipient_pubkey, message, []))
            else:
                asyncio.run(self._send_nip04_dm(relay_urls, recipient_pubkey, message))
            logger.info("published Nostr DM: {}".format(event.summary))
            self.no_more_logging()
            return True
        except Exception as exc:
            logger.critical("Nostr publish failed: {}".format(str(exc)))
            return False
