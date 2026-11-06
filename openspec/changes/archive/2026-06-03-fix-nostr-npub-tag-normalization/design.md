## Context

The archived Nostr change introduced support for publishing monitoring notifications as signed notes and documented a `p` tag for recipient targeting. In practice, operators are more likely to exchange recipient keys as `npub` strings, while Nostr relay payloads still need the underlying public key form.

## Goals / Non-Goals

**Goals:**
- Accept recipient keys in `p` tags as either `npub...` or raw hex.
- Convert `npub...` values to hex at publish time.
- Preserve existing behavior for all other tags and note content.
- Keep the fix backward-compatible for existing hex-based configurations.

**Non-Goals:**
- Changing the Nostr event schema beyond recipient tag normalization.
- Adding new tag types or changing relay selection logic.
- Introducing new cryptographic behavior.

## Decisions

- Normalize only `p` tags, because that is the recipient-public-key tag where the format mismatch matters.
- Prefer a runtime conversion in the forwarder instead of pushing format handling into operator docs or requiring manual conversion.
- Keep the original tag shape intact for non-`p` tags so the change stays narrow and low-risk.
- Treat raw hex as a first-class supported input so existing configs continue to work unchanged.

## Risks / Trade-offs

- [Risk] A malformed `npub` value could still be passed in. → Mitigation: leave invalid values visible and rely on existing publish-path failure handling rather than silently rewriting unrelated tags.
- [Risk] The acceptance of two input formats may be surprising to future contributors. → Mitigation: document both formats in the spec and code comment near the forwarder.
- [Trade-off] Conversion happens at publish time instead of earlier in the pipeline. → This keeps the formatter simple and confines format handling to the component that needs it.
