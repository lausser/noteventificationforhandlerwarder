## Context

The current Nostr implementation uses `pynostr` and manually constructs encrypted direct messages. That approach is tied to NIP-04-style DMs and does not align with NIP-17 private messages. `nostr-sdk` exposes higher-level private-message APIs, but it is explicitly alpha and its Python FFI surface may change.

## Goals / Non-Goals

**Goals:**
- Publish NIP-17 private messages using `nostr-sdk`.
- Keep notificationforwarder's public behavior stable where practical.
- Contain the alpha-library risk behind a small adapter surface.
- Preserve relay configuration, recipient selection, and retry semantics as much as possible.

**Non-Goals:**
- Re-implement the Nostr protocol stack ourselves.
- Support every possible `nostr-sdk` feature in v1.
- Freeze the `nostr-sdk` API surface; upstream owns that.

## Decisions

- Move Nostr direct-message construction into a library adapter that wraps `nostr-sdk`.
  - Rationale: NIP-17 requires more than changing an event kind; the library can handle sealing, wrapping, relay selection, and signing details.
  - Alternative considered: keep `pynostr` and manually emulate NIP-17. Rejected because the library model and docs are NIP-04-oriented.

- Keep the adapter boundary small and synchronous from the caller's perspective.
  - Rationale: notificationforwarder is structured around a synchronous submit pipeline, so the async `nostr-sdk` API should be hidden behind a narrow bridge.
  - Alternative considered: convert the whole notificationforwarder Nostr path to async end-to-end. Rejected as a larger cross-cutting change.

- Treat `nostr-sdk` as a high-risk dependency and isolate breakage.
  - Rationale: the library is alpha and may ship breaking API changes; this change should be easy to adapt or roll back.
  - Alternative considered: wait for stable release. Rejected because the current implementation cannot correctly target NIP-17.

- Preserve current operational knobs where feasible.
  - Rationale: relay URLs, recipient identity, and retry behavior matter more to operators than the underlying client library.

## Risks / Trade-offs

- [Alpha API churn] Upstream may rename or reshape the Python API -> Mitigate by keeping a thin adapter and pinning versions.
- [Native dependency/install issues] Wheels or platform support may lag -> Mitigate by documenting supported environments and testing install paths in CI.
- [Async integration complexity] Bridging async `nostr-sdk` into the current sync pipeline may introduce edge cases -> Mitigate by containing the event loop handling in one module.
- [Operational regression] NIP-17 behavior differs from the old DM flow -> Mitigate by updating docs and tests to reflect the new protocol semantics.

## Migration Plan

1. Introduce a small compatibility layer for Nostr publishing.
2. Swap the implementation from `pynostr` to `nostr-sdk` behind that layer.
3. Update tests to cover private-message publication and error handling.
4. Validate packaging and runtime installation on supported environments.
5. Roll back by restoring the compatibility layer to the previous backend if `nostr-sdk` proves unstable.

## Open Questions

- Which `nostr-sdk` Python API surface should we target for the first implementation version?
- Do we need a hard version pin to avoid alpha-breaking changes in production installs?
- Should the new integration require explicit NIP-17 relay discovery, or should it accept operator-provided relays only?
