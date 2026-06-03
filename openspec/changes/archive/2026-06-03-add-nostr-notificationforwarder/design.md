## Context

`notificationforwarder` already separates event shaping from delivery, which maps well to Nostr's split between note construction and relay publishing. Nostr publishing also requires signed events and relay communication, so the integration needs protocol-specific behavior that should stay isolated from the existing webhook path.

## Goals / Non-Goals

**Goals:**
- Publish monitoring notifications to one or more Nostr relays.
- Keep the integration small, plugin-based, and backward-compatible.
- Preserve the existing formatter/forwarder contract so other notification targets are unaffected.
- Use a maintained Python Nostr library instead of hand-rolling protocol, signing, and relay logic.

**Non-Goals:**
- Building a generic Nostr client framework.
- Supporting advanced relay management, subscriptions, or multiple event kinds.
- Changing `eventhandler` behavior.
- Reworking the webhook forwarder unless the Nostr protocol can be represented safely and clearly there.

## Decisions

- **Use a dedicated Nostr forwarder**: webhook transport is HTTP-oriented, while Nostr needs signed relay events. A dedicated forwarder keeps the protocol boundary obvious and keeps retry/failure behavior honest.
- **Use `pynostr`**: it is the best fit for relay publishing and key handling among the candidate Python libraries we reviewed, and it keeps cryptographic and network details out of local code.
- **Keep the formatter narrow**: the formatter should turn OMD fields into a readable Nostr note body plus a small tag set. The forwarder should own signing, relay selection, and publish results.
- **Use a structured note body**: format notes as labeled lines in a markdown-like block (`Host:`, `Service:`, `State:`, `Output:`) so the message is readable in Nostr clients without requiring a template engine.
- **Standardize on `nsec` secrets**: accept `nsec`-encoded private keys only. That avoids ambiguity about key parsing and reduces the chance of accidentally logging raw hex material.
- **Add monitoring and event tags**: include `monitoring` plus event-specific tags for host, service, and state by default, unless explicitly overridden by configuration.
- **Document keypair generation in the formatter**: include a short header comment in `nostr/formatter.py` with a `pynostr` snippet that shows how to create a keypair and derive `nsec`/`npub`, so operators have a local reference without searching external docs.

## Risks / Trade-offs

- [Protocol complexity] → Limit scope to text-note publishing with a small set of relay and key options.
- [Dependency risk] → Keep the dependency isolated behind the forwarder so a library swap does not affect the public plugin contract.
- [Relay reliability] → Treat publish failures as forwarder failures so the existing spool/retry behavior can handle temporary outages.
- [Secret handling] → Accept keys only through existing option mechanisms and never log the secret material.

## Migration Plan

1. Add the new Nostr plugin modules and dependency behind the existing plugin loading model.
2. Implement formatter and forwarder behavior with a small default configuration surface.
3. Add tests for payload shaping, relay publish success, and failure handling.
4. Document the new options and verify the existing webhook forwarder remains unchanged.
