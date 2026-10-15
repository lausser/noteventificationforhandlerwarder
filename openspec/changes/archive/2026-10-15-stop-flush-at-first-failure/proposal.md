# Proposal

## Why

When a receiver such as ServiceNow is down, a flush currently keeps submitting until a whole batch of 10 events has failed. With the shipped 30 s submit timeout (`@timeout(30)`) a single flush can take up to 5 minutes, far longer than Naemon's default `notification_timeout` of 30 s. An outage of the receiver is far more likely than a one-time network hiccup, so after the first failure the following submits will almost certainly fail too. Customers keep events for up to five days (`max_spool_minutes=7200`), so a long outage produces a large backlog, and every notification process pays these timeouts.

Stopping at the first failure introduces a new risk: an event that the receiver rejects permanently (for example HTTP 400 for a broken payload) would block every flush until it expires, up to five days. The change therefore also moves such an event to the end of the spool once the receiver has demonstrably accepted another event.

## What Changes

- A flush stops at the first spooled event whose replay fails (submit returns failure or raises, including the submit timeout). It logs "event stays in spool" for that event and the existing critical "spooled events could not be submitted". Discarded and unformattable events are still removed and do not stop the flush.
- If the flush stopped at a failed event and the live event of the same process is then submitted successfully, the stopped event is moved to the end of the spool: it gets a new id behind all other events, keeps its payload and original timestamp, and therefore still expires on schedule. A critical log names the moved event.
- The move only happens while holding the flush lock. If another process holds the lock, the move is skipped; the next flush that stops at the same event will try again.
- Side effect: a flush no longer delivers later spooled events past a failed one, which removes one of the cases in which events reached the receiver out of order. The "Delivery Order" section in the README and INDEX is updated.

## Non-goals

- Strict delivery order. Live events are still submitted directly, as before.
- Distinguishing permanent from temporary failures in forwarder plugins.
- Changing the submit timeouts, the flush lock protocol, the batch size, or the spool schema.
- Protecting the live event of a process that Naemon kills during a long submit.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `delivery-resilience`: the flush stops at the first failed replay instead of after a batch without progress, and an event that fails while the receiver accepts other events is moved to the end of the spool.

## Impact

- **Code**: `notificationforwarder/src/notificationforwarder/baseclass.py` (`flush()`, `forward_formatted()`), `notificationforwarder/src/notificationforwarder/spool.py` (new `move_to_end()`), `notificationforwarder/src/notificationforwarder/text/logger.py` (message for the move), `notificationforwarder/src/notificationforwarder/json/logger.py` (`new_event_id`)
- **Tests**: `notificationforwarder/tests/test_resilience_spool.py` (two existing tests change their expectations, new tests for the stop and the move), `notificationforwarder/tests/test_loggers.py`
- **Docs**: `notificationforwarder/README.md`, `notificationforwarder/INDEX.md`, `notificationforwarder/tests/TESTS.md`
- **Dependencies**: none
- **Behavior**: during an outage a flush costs at most one submit timeout instead of up to ten. A permanently rejected event no longer blocks the backlog once any other event gets through. It moves to the end at most once per successful live submit and is dropped when it expires.
