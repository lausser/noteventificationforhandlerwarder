## 1. Fix missing import

- [x] 1.1 Add `resolve_identity_file` to the import in `eventhandler/src/eventhandler/ssh/runner.py`

## 2. Add test coverage

- [x] 2.1 Add test in `eventhandler/tests/test_contracts_runners.py` that instantiates `SshRunner` with `identity_file="~/.ssh/id_rsa"` and verifies the resolved absolute path
- [x] 2.2 Run eventhandler test suite to verify the fix and new test pass
