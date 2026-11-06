## 1. Runtime Foundation

- [ ] 1.1 Refactor `eventhandler` baseclass flow so enrichment, decider loading, event preparation, execution, forwarding, and logging are distinct checkpoints.
- [ ] 1.2 Normalize runtime path and environment resolution for log, temp, and identity-derived files.
- [ ] 1.3 Improve component-loading errors for deciders, runners, forwarders, and loggers with actionable context.

## 2. Execution and Recovery

- [ ] 2.1 Make runner execution outcomes explicit for success, failure, and silent discard paths.
- [ ] 2.2 Clarify optional forwarder handoff behavior and preserve event context on downstream failure.
- [ ] 2.3 Tighten concurrency and recovery safeguards so overlapping retries or replay attempts are suppressed predictably.

## 3. Tests and Documentation

- [ ] 3.1 Add or update tests covering dynamic loading, logger fallback, execution failure handling, forwarding, and recovery flows.
- [ ] 3.2 Update contributor documentation for deciders, runners, forwarders, and logging/runtime expectations.
- [ ] 3.3 Verify the full eventhandler test suite passes with the new runtime behavior.
