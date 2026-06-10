## 1. Native Logging Implementation

- [x] 1.1 Create `notificationforwarder/util.py` with minimal `setup_logging()` function
- [x] 1.2 Create `eventhandler/util.py` with minimal `setup_logging()` function
- [x] 1.3 Implement console handler output to stderr
- [x] 1.4 Use same log format: `%(asctime)s %(process)d - %(levelname)s - %(message)s`
- [x] 1.5 Do NOT implement state preservation or runtime logfile switching

## 2. Integration into notificationforwarder

- [x] 2.1 Update `notificationforwarder/src/notificationforwarder/baseclass.py` to import `setup_logging` from local util module
- [x] 2.2 Update any other modules in notificationforwarder that import `setup_logging` from coshsh
- [x] 2.3 Remove coshsh from notificationforwarder runtime and build dependencies
- [x] 2.4 Verify formatter module logging still lands in the runtime logfile
- [x] 2.5 Test that logging still works identically in notificationforwarder

## 3. Integration into eventhandler

- [x] 3.1 Update `eventhandler/src/eventhandler/baseclass.py` to import `setup_logging` from local util module
- [x] 3.2 Update any other modules in eventhandler that import `setup_logging` from coshsh
- [x] 3.3 Remove coshsh from eventhandler runtime and build dependencies
- [x] 3.4 Test that logging still works identically in eventhandler

## 4. Testing and Validation

- [x] 4.1 Run existing test suite for notificationforwarder to verify no behavior changes
- [x] 4.2 Run existing test suite for eventhandler to verify no behavior changes
- [x] 4.3 Verify test_classes.py tests still pass (logging without/with tag)
- [x] 4.4 Verify test_runtime_foundation.py tests still pass (logger name with tag)
- [x] 4.5 Verify test_notify.py tests still pass (actual log file creation with tags)
- [x] 4.6 Add/verify a formatter-logging test so module-level formatter logs reach the runtime logfile
- [x] 4.7 Test in OMD environment to ensure backward compatibility
- [x] 4.8 Verify log format matches the current output exactly

## 5. Documentation

- [x] 5.1 Update README in notificationforwarder to reflect removed coshsh dependency
- [x] 5.2 Update README in eventhandler to reflect removed coshsh dependency
- [x] 5.3 Add note about native logging implementation in developer docs
- [x] 5.4 Update changelog with the change
