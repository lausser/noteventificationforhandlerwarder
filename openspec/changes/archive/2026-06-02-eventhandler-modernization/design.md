## Context

`eventhandler` is a plugin-driven runtime that loads deciders and runners dynamically, enriches incoming events, executes commands or Python-side actions, and synchronously forwards results onward. The current implementation already supports these behaviors, but the orchestration layer has accumulated responsibility around loading, logging, forwarding, and execution details, which makes correctness and maintainability harder to preserve as the code evolves.

This change should modernize `eventhandler` in the same spirit as the recent `notificationforwarder` work: preserve behavior where operators depend on it, but make the runtime flow easier to understand, test, and extend. The target is not just cleanup; it is homogeneity with `notificationforwarder` in concepts, module layout, and runtime style.

## North Star

- Match `notificationforwarder` in runtime shape: config, loader, flow, orchestration.
- Keep `runtime_flow` thinner because `eventhandler` has no spool/retry layer.
- Preserve synchronous forwarding and existing runner compatibility.
- Keep `TextLogger` and `JsonLogger` output styles, but refactor them behind the sibling-style loading/fallback pattern.
- Use purpose-driven helper names that fit eventhandler semantics.
- Make the preferred execution path obvious without breaking older valid paths.
- Ensure logs and errors explain what failed, where it failed, and what the runtime did next.

## Goals / Non-Goals

**Goals:**
- Match `notificationforwarder`'s architecture with the same conceptual split: `runtime_config`, `component_loader`, `runtime_flow`, and a lean orchestration baseclass.
- Keep synchronous forwarding and preserve current forwarding semantics.
- Retain runner compatibility (`str` / `bool` / `None`) while steering the runtime toward one preferred execution style.
- Normalize logger loading, fallback behavior, and structured context handling to match the sibling runtime.
- Improve contributor-facing documentation and tests for the runtime contract.

**Non-Goals:**
- Redesigning the plugin model or removing existing runner/decider entry points.
- Introducing new external service dependencies.
- Changing the user-facing CLI shape unless needed to support existing behavior more consistently.

## Decisions

1. Split `eventhandler` into the same runtime modules used by `notificationforwarder`.
   - Rationale: the clearest way to make the two tools feel like siblings is to align the runtime structure itself, not just the surface behavior.
   - Alternatives considered: leaving everything in `baseclass.py` with helper functions would reduce churn, but it would preserve the current coupling and make the codebase feel different from `notificationforwarder`.

2. Keep the dynamic decider/runner loading model, but make resolution and errors more explicit.
   - Rationale: the plugin architecture is core to the project and should stay flexible.
   - Alternatives considered: static registration or hard-coded imports would simplify loading but would reduce extensibility and break established usage patterns.

3. Preserve the current event mutation contract, but wrap it in clearer runtime checkpoints.
   - Rationale: existing deciders already mutate event objects; changing to a return-value model would be a broad compatibility shift.
   - Alternatives considered: immutable event transforms or new dataclasses would be cleaner conceptually, but they would require more migration effort and more invasive code changes.

4. Centralize synchronous forwarding behavior behind a clearly bounded integration path.
   - Rationale: forwarding is a secondary concern and should not obscure primary runner execution, but it should remain synchronous to preserve current operational semantics.
   - Alternatives considered: asynchronous forwarding would decouple execution from delivery, but it would diverge from the current model and from the desired sibling alignment.

5. Standardize runtime logging and error reporting around consistent event context.
   - Rationale: operators need readable logs that tie together the original event, the decision taken, and the execution result.
   - Decision: keep the current `TextLogger` and `JsonLogger` output styles, but refactor them behind the same logger-loading pattern, fallback behavior, and structured-context plumbing used by `notificationforwarder`.
   - Alternatives considered: rewriting the message bodies to match `notificationforwarder` exactly, which would be more disruptive than necessary.

6. Expand test coverage around orchestration boundaries rather than internal implementation details.
   - Rationale: the risky behavior is in composition, loading, and failure handling.
   - Alternatives considered: low-level unit tests only, which would miss regressions in the end-to-end runtime flow.

## Risks / Trade-offs

- [Refactoring the runtime flow may expose hidden assumptions] → Mitigate with incremental changes and coverage around existing plugin behavior.
- [Stricter error handling could surface failures that were previously silent] → Mitigate by preserving documented discard, forwarding, and compatibility semantics while improving messages.
- [Improved structure will touch multiple modules at once] → Mitigate by mirroring the `notificationforwarder` split and keeping the public plugin contract stable.
- [More explicit logging can increase noise] → Mitigate by keeping logs focused on outcome, context, and recovery signals.

## Migration Plan

1. Extract shared runtime concepts into sibling modules with the same naming and responsibility split as `notificationforwarder`.
2. Move orchestration out of `baseclass.py` into smaller helpers while keeping the existing CLI and plugin entry points stable.
3. Refactor built-in loggers, runners, and deciders to consume the new runtime helpers and structured context.
4. Refactor `TextLogger` and `JsonLogger` to use the sibling-style loading and fallback pattern while preserving their output formats.
5. Run the full `cd eventhandler; pytest` suite after each meaningful refactor step to catch compatibility regressions early.
6. Preserve synchronous forwarding and current return-mode compatibility throughout the migration.

Rollback strategy: if a refactor step changes behavior unexpectedly, revert the smallest affected runtime split and keep the preexisting orchestration path intact until the surrounding tests are restored.

## Open Questions

- The new module split should be structurally similar to `notificationforwarder`, but `runtime_flow` can be thinner because `eventhandler` has no spool/retry layer.
- `TextLogger` and `JsonLogger` should keep their current output styles while adopting the same loader/fallback structure as the sibling runtime.
- Helper names should be purpose-driven and fit eventhandler semantics, not force exact naming parity with `notificationforwarder`.
