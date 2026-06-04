## Context

The current Nostr forwarder has grown a local compatibility layer around `pynostr`, including stand-in classes for cryptographic and relay primitives. That makes the module harder to reason about and blurs the dependency boundary: the code appears optional, but the feature is really only meaningful when the real library is present.

## Goals / Non-Goals

**Goals:**
- Make `pynostr` a hard dependency for the Nostr forwarder.
- Remove duplicate fallback behavior that imitates third-party classes.
- Preserve the existing error path so the baseclass remains responsible for logging and aborting failed startup/imports.
- Keep runtime behavior unchanged when `pynostr` is installed.

**Non-Goals:**
- Reworking the Nostr formatter payload shape.
- Changing relay fan-out or DM message semantics.
- Adding a new plugin abstraction or compatibility layer.

## Decisions

- **Fail fast on import**: If `pynostr` cannot be imported, the module should not attempt to continue with local substitutes. This keeps the dependency contract obvious and avoids silently diverging behavior.
  - Alternative considered: keep fallback shims for testability. Rejected because they duplicate library behavior and hide missing-dependency failures.
- **Keep error handling one layer up**: The forwarder should let the import exception propagate to the baseclass, which already logs and aborts appropriately.
  - Alternative considered: catch and downgrade the error inside the forwarder. Rejected because it adds another failure path and weakens the hard-dependency contract.
- **Tests should validate absence of fallback**: Verification should focus on missing-dependency failure and unchanged success path with real `pynostr`.
  - Alternative considered: preserve the shim and test both code paths. Rejected because the shim is the problem being removed.

## Risks / Trade-offs

- [Users without `pynostr` installed can no longer instantiate the forwarder] -> This is intentional; document the dependency clearly and keep the failure message explicit.
- [Tests may need the real library available] -> Use targeted tests or environment markers so the suite can still distinguish dependency-missing behavior from normal behavior.
- [Removing fallback code can surface hidden assumptions] -> Run the Nostr tests against the real library and verify the normal publish path still passes.
