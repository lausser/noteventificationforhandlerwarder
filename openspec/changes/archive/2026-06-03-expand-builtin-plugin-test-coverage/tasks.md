## 1. Inventory and gap analysis

- [x] 1.1 Map every built-in notificationforwarder plugin module to an existing or missing test file.
- [x] 1.2 Map every built-in eventhandler plugin module to an existing or missing test file.
- [x] 1.3 Identify logger, loader, fallback, discard, retry, and failure paths that lack direct assertions.

## 2. notificationforwarder coverage

- [x] 2.1 Add or expand tests for built-in formatters to cover normal payload creation and edge-case inputs.
- [x] 2.2 Add or expand tests for built-in forwarders to cover success, authentication, transport failure, and timeout/spool behavior.
- [x] 2.3 Add or expand tests for built-in reporter behavior, including successful reporting and failure logging.
- [x] 2.4 Add or expand tests for built-in logger modules and logger fallback behavior.

## 3. eventhandler coverage

- [x] 3.1 Add or expand tests for built-in deciders to cover prepare/discard decisions and boundary conditions.
- [x] 3.2 Add or expand tests for built-in runners to cover command execution, direct-return outcomes, failure propagation, and timeout behavior.
- [x] 3.3 Add or expand tests for eventhandler notification forwarding to notificationforwarder on success and failure.

## 4. Cross-cutting regression verification

- [x] 4.1 Add tests that verify dynamic loading resolves built-in modules and local overrides correctly.
- [x] 4.2 Add tests for failure paths that should not crash the orchestration flow, including downstream forwarder/reporting failures.
- [x] 4.3 Run the relevant test subsets for both subprojects and fix any regressions uncovered by the new coverage.
