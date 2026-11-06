# Proposal

## Why

Operators alert on the spool queue length by scraping `"message":"spooling queue length","queue_length":N` from the log. That line is only written when an event is spooled, so while the queue drains after an outage no new value is logged and the last scraped value stays at its peak until the next delivery fails. Until 4.4, "spooled events to be re-sent" happened to carry the whole spool size; since 4.5 it carries the batch size, so there is no log line that reports the queue shrinking.

## What Changes

- At the end of every flush that got the flush lock, the remaining number of spooled events is logged as "spooling queue length" with `queue_length`, at info level (the existing line written when an event is spooled stays at warning level).
- The value is the whole spool, including events spooled by other processes while the flush ran.
- The README and INDEX describe the line as the value to monitor.

## Non-goals

- Logging the queue length when no flush runs (no notifications, or `probe()` fails). The value is only as fresh as the last notification; the README points to the spool database for a check that does not depend on notifications.
- Changing the meaning of "spooled events to be re-sent" or "spooled events could not be submitted".

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `delivery-resilience`: every flush logs the remaining spool size, so the queue length can be observed while it shrinks.

## Impact

- **Code**: `notificationforwarder/src/notificationforwarder/baseclass.py` (`flush()`)
- **Tests**: `notificationforwarder/tests/test_resilience_spool.py`, `notificationforwarder/tests/TESTS.md`
- **Docs**: `notificationforwarder/README.md`, `notificationforwarder/INDEX.md`
- **Behavior**: one additional info line per flush; no change to delivery.
