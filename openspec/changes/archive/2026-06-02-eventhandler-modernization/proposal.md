## Why

`eventhandler` still works, but its runtime is harder to reason about than it should be: decision logic, command execution, forwarder integration, and operational logging are tightly coupled. Modernizing it now will make the event flow more elegant, reliable, and maintainable while keeping the practical automation behavior intact.

## What Changes

- Refine the eventhandler runtime so enrichment, decision-making, command execution, forwarding, and logging each have clearer responsibilities.
- Improve failure handling for runner execution, forwarder handoff, and discard paths so outcomes are deterministic and easier to debug.
- Standardize configuration, environment resolution, and per-event option overrides to reduce hidden behavior.
- Strengthen test coverage around core runtime behavior, especially decider loading, runner execution, forwarding, and error handling.
- Refresh documentation so contributor expectations and operational guarantees are easier to understand.

## Capabilities

### New Capabilities

- `runtime-foundation`: Defines a clearer core runtime contract for decider loading, event enrichment, command execution, forwarding, and logging coordination.
- `delivery-resilience`: Defines reliable forwarding and recovery behavior for failed runner or forwarder outcomes, including retry/spool semantics where applicable.
- `developer-experience`: Defines maintainable extension and documentation expectations for contributors adding deciders, runners, forwarders, and related runtime integrations.

### Modified Capabilities

- `runtime-foundation`: Existing runtime expectations are extended to cover `eventhandler` orchestration and lifecycle behavior.
- `delivery-resilience`: Failure handling requirements are broadened to include eventhandler execution and downstream notification handoff.
- `developer-experience`: Contributor-facing guidance and tests are expanded to include eventhandler-specific extension patterns and guarantees.

## Impact

- Affected code: `eventhandler/src/eventhandler/baseclass.py`, built-in deciders/runners, CLI entrypoints, and tests.
- Affected systems: command execution flow, optional forwarding behavior, logging, and runtime environment handling.
- Dependencies and APIs: no planned user-facing API removal, but internal contracts and tests will be tightened to support a more modern implementation.
