## Context

`notificationforwarder` is a Python framework that transforms monitoring events into payloads and forwards them to downstream systems. The current implementation delivers real value, but much of the runtime behavior is concentrated in `baseclass.py`, where dynamic imports, logging setup, environment/path initialization, sqlite spooling, timeout handling, flush behavior, and event flow are tightly coupled.

This coupling makes the system harder to evolve safely. A failure in one area can affect unrelated behavior, and the current structure makes both testing and contributor onboarding more expensive than necessary. The project also needs clearer operational guarantees around what happens when a delivery fails, when a retry is attempted, and how those outcomes are logged.

Constraints:
- The project remains a Python package used in OMD/monitoring environments.
- Existing built-in forwarder, formatter, reporter, and logger concepts stay intact.
- The notification forwarder can be used in the companion tool `eventhandler`.
- Modernization should preserve the practical extension model while making the internals easier to reason about and test.

## Goals / Non-Goals

**Goals:**
- Split core runtime responsibilities into clearer units with explicit boundaries.
- Define deterministic behavior for component loading, event forwarding, failure handling, spooling, and flush/retry flows.
- Reduce hidden global side effects, especially around logger initialization and module wiring.
- Make the runtime easier to validate with focused automated tests.
- Improve contributor documentation for extending the framework safely.

**Non-Goals:**
- Replacing the plugin model with a new extension system.
- Introducing a network service, daemon, or external queue.
- Rewriting all built-in forwarders/formatters for style alone.
- Changing user-facing command semantics unless required by the new specs.

## Decisions

### Decision: Separate runtime orchestration from plugin implementations
The runtime should be organized around a small orchestration layer that coordinates loading, formatting, forwarding, reporting, logging, and spooling rather than embedding all of that behavior directly in one monolithic base class.

Rationale:
- Clearer ownership reduces incidental coupling and makes behavior easier to test in isolation.
- Runtime orchestration becomes easier to inspect and document.

Alternatives considered:
- Keep everything in `baseclass.py` and add comments/tests. Rejected because it improves understanding only superficially and leaves the same structural risk in place.
- Fully rewrite the package around a new framework. Rejected because it creates unnecessary migration risk.

### Decision: Introduce explicit runtime contracts for loading and lifecycle
Component loading for forwarders, formatters, reporters, and loggers should be normalized behind explicit loader behavior with validated naming rules, well-defined fallback behavior, and actionable error reporting.

Rationale:
- The current dynamic import approach is flexible but opaque when something fails.
- Explicit contracts reduce contributor guesswork and improve debuggability.

Alternatives considered:
- Hardcode a registry for every built-in plugin. Rejected because local/site-specific extension loading is a core strength of the project.

### Decision: Treat spool persistence as a first-class reliability boundary
The spool database, locking, retention, and flush flow should be treated as a distinct reliability concern with consistent invariants: failed events are either durably recorded or explicitly reported as not recoverable, retried events are observable, and expired events are handled predictably.

Rationale:
- Delivery resilience is central to the product value.
- Spooling behavior is currently important but buried inside general runtime flow.

Alternatives considered:
- Leave spool behavior implicit inside forwarder execution. Rejected because reliability requirements deserve direct tests and explicit guarantees.

### Decision: Keep compatibility by modernizing internally first
The implementation should prefer internal refactoring and better contracts over broad user-visible changes. Existing extension naming conventions and existing runtime entrypoints should remain functional unless a clearly justified behavior change is specified.

Rationale:
- This change aims to improve trust and maintainability, not to force users onto a new model.
- Compatibility-first modernization reduces rollout risk.

Alternatives considered:
- Break old extension assumptions immediately. Rejected because there is no evidence that disruption is necessary for the desired outcomes.

### Decision: Expand test coverage around failure modes, not just happy paths
Tests should directly cover loader errors, formatter/forwarder/reporter failures, timeout behavior, spool insertion, flush ordering, expiration handling, and logger selection/fallback.

Rationale:
- The system is most valuable when downstream systems fail or degrade.
- Confidence in the redesign depends on proving those paths, not only nominal flows.

Alternatives considered:
- Limit coverage expansion to smoke tests. Rejected because that would not protect the critical reliability guarantees this change is meant to strengthen.

## Risks / Trade-offs

- Refactoring core runtime logic could introduce regressions in extension loading or delivery order. -> Mitigation: preserve current entrypoints, add characterization tests before and during refactoring, and validate built-in plugins through integration-style tests.
- Clarifying behavior may expose existing ambiguous or inconsistent semantics that some deployments accidentally rely on. -> Mitigation: prefer compatibility where feasible, document intentional behavior changes explicitly, and keep spec changes narrow and testable.
- More explicit contracts may require additional helper modules or types. -> Mitigation: keep the design minimal and introduce only the seams needed to separate responsibilities and improve tests.
- Better failure reporting can increase visible log output. -> Mitigation: keep logs structured and focused on actionable runtime state rather than verbose duplication.

## Migration Plan

1. Capture current behavior with tests around the existing runtime flow.
2. Refactor internals incrementally behind current public entrypoints.
3. Update built-in plugins only where necessary to align with clarified contracts.
4. Refresh documentation after the runtime behavior and extension expectations are stable.
5. Run the full test suite and targeted reliability scenarios before release.
6. Run pytest on any change to Python files.

Rollback strategy:
- Because this change primarily targets internal structure, rollback is a code revert to the prior runtime implementation if regression risk proves too high before release.

## Open Questions

- Should sqlite access remain embedded in the runtime package, or should it be isolated behind a minimal persistence adapter from the start?
-->Answer: create a simple persistence layer.
- Which existing edge-case behaviors are intentionally relied on by current deployments and therefore must be preserved exactly?
-->Answer: no known edge cases
- Is a small typed configuration object worthwhile now, or should option normalization stay dictionary-based for the first modernization pass?
-->Answer: it is worthwile
