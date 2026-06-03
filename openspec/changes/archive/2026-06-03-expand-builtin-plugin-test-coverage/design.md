## Context

This change is a test-coverage hardening pass across both Python subprojects. The runtime already supports a wide range of built-in plugins, but the current test suite is uneven: some modules have direct coverage, others are only exercised indirectly, and failure behavior is not always asserted at the boundary where users observe it.

The main stakeholders are contributors changing plugin implementations and operators relying on stable failure handling, retry behavior, and logging.

## Goals / Non-Goals

**Goals:**
- Ensure every built-in formatter, forwarder, reporter, decider, runner, and logger has explicit test coverage.
- Cover both success paths and important failure/edge cases.
- Preserve existing runtime behavior while increasing regression protection.
- Make the test suite document the intended behavior of dynamic loading, logger fallback, delivery recovery, and eventhandler-to-notification forwarding.

**Non-Goals:**
- No runtime feature additions.
- No API redesign for plugin loading or event objects.
- No new plugin types or external dependencies.
- No broad refactor of the base classes beyond what testability requires.

## Decisions

- Add focused regression tests per built-in module group rather than one large end-to-end test per subproject.
  - Rationale: smaller tests make failures easier to localize and maintain.
  - Alternative considered: only expand existing integration tests. Rejected because it would keep module-specific gaps hidden.

- Prefer observable behavior assertions over import-only checks.
  - Rationale: loading a module successfully does not prove its runtime contract or failure behavior.
  - Alternative considered: snapshot-style log assertions only. Rejected because logs alone do not verify state, payloads, or side effects.

- Reuse existing OMD-style fixtures and local pythonpath overrides.
  - Rationale: keeps tests aligned with the current runtime environment and avoids new test harness complexity.
  - Alternative considered: introducing new fixtures or mock loaders. Rejected because it would diverge from real module resolution.

- Treat logger fallback, spooling, retry, and discard paths as first-class regression targets.
  - Rationale: these are the most failure-sensitive behaviors in production.
  - Alternative considered: cover them indirectly through happy-path tests. Rejected because failures must be asserted explicitly.

## Risks / Trade-offs

- More tests may increase runtime. → Keep coverage focused per module and prefer deterministic unit/integration hybrids.
- Some edge cases may depend on environment-specific timing or filesystem behavior. → Use isolated temp OMD roots and explicit assertions around files, logs, and return codes.
- The suite may reveal pre-existing bugs. → Capture those as failing tests first, then fix incrementally without weakening assertions.
