## Context

The Nostr forwarder depends on `pynostr`, and its startup path currently produces a repeated websocket timeout warning even in successful runs. The warning is not actionable for operators and obscures real issues during notification forwarding.

The change should be narrow, preserve the existing runtime model, and avoid altering Nostr delivery semantics or the fail-fast behavior for missing dependencies.

## Goals / Non-Goals

**Goals:**
- Remove the known startup warning from normal `notificationforwarder` Nostr runs.
- Keep relay publishing behavior unchanged.
- Keep the dependency failure path unchanged.
- Limit the fix to the smallest practical code surface.

**Non-Goals:**
- Redesign Nostr support.
- Replace `pynostr`.
- Add new user-facing configuration unless it is strictly needed.

## Decisions

- **Prefer a local, narrowly scoped suppression or configuration adjustment at the warning source.** This keeps the change minimal and avoids suppressing unrelated warnings elsewhere in the process.
  - Alternatives considered: patching `pynostr` upstream only, redirecting all stderr output globally, or accepting the warning as harmless.
  - Rationale: upstream fixes may not be immediately available, and global suppression is too blunt.

- **Preserve existing relay and import behavior.** The forwarder should still fail fast if `pynostr` is unavailable and should still publish exactly as before once initialized.
  - Alternatives considered: catching and ignoring broader initialization errors or swapping websocket parameters more aggressively.
  - Rationale: the change should address only the noisy warning, not mask real runtime failures.

- **Keep regression coverage focused on observable output and startup success.** Tests should assert that the warning no longer appears in the common path while the forwarder still initializes and can proceed with publishing.
  - Alternatives considered: only manual verification.
  - Rationale: the issue is user-visible and should be protected by automated checks.

## Risks / Trade-offs

- [Risk] Suppressing the message too broadly could hide useful warnings → [Mitigation] Scope suppression to the known `pynostr` startup path only.
- [Risk] A dependency update could change the message text or origin → [Mitigation] Keep the fix small and verify against the current dependency version.
- [Risk] A tiny local patch may diverge from upstream behavior → [Mitigation] Prefer minimal, well-commented code and revisit when upstream resolves the issue.

## Migration Plan

No data migration is required.

Deployment should be safe as a normal application update:
1. Ship the code change.
2. Verify the Nostr forwarder starts without the warning.
3. Confirm relay publishing still succeeds.

Rollback is the standard application rollback to the previous version if unexpected side effects appear.

## Open Questions

- Should the implementation silence only the exact warning text, or should it adjust the websocket configuration if that achieves the same effect cleanly?
- Is there a stable upstream `pynostr` fix available in the dependency range used here?
