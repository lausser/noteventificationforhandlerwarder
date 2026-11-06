# Proposal

## Why

A user complained that when a spooled event is deleted from the spool, the "delete" log line shows only the database record id, while the "spooling" log line shows the event content but no id. There is no way to correlate the two lines, so the operator cannot tell which original event a delete line refers to. Every spool-related log line should be self-sufficient: carrying both the event id and the event content, so no piece of information can get lost.

## What Changes

- `SpoolStore.enqueue()` returns the new row id (`lastrowid`); `NotificationForwarder.spool()` propagates it so the spool-time log line (forward failed) gains the `event_id`.
- The spool-time log line (forward failed) also carries the decoded raw event passed to `enqueue()` — the exact payload stored in the spool — and the summary when the formatted event has one.
- All delete/stay/discard log lines in the flush replay loop gain event content: `summary` (when a summary exists) and `raw_event` (always), alongside the existing `event_id`. The logged raw event retains the stored payload independently of formatter and forwarder mutations.
- `SpoolStore.prune_expired()` returns the expired rows so the baseclass logs one line per expired event (with its id and raw event payload) in addition to the existing aggregate count line.
- Both shipped loggers render the new fields, because they are rendering layers that decide what reaches the log target: the text logger's message templates and the JSON logger's field allowlist must be extended for every affected line (`text/logger.py`, `json/logger.py`).
- A small context-builder supplies the event fields consistently and degrades gracefully when no summary exists (formatter failed hard): the `summary` field is omitted unless the formatted event has a non-empty summary, and the raw event carries the content.
- Log lines for the move-to-end path already contain both old and new ids and remain unchanged.
- All affected log lines satisfy the operator's question from any single line: "which event is behind this id?"

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `delivery-resilience`: the structured/replay observability requirements are extended — spool-time, delete-time, and expiry log lines SHALL carry both the event id (spool/delete/move paths) and the event content (summary when available, raw event always), including per-event logging of expired spool entries at flush time.

## Impact

- `notificationforwarder/src/notificationforwarder/spool.py`: `enqueue()` return value; `prune_expired()` SELECT before DELETE and new return value (list of expired rows instead of a count).
- `notificationforwarder/src/notificationforwarder/baseclass.py`: `spool()` internal return contract (its caller in `forward()` plus two tests that stub/call it), spool-time log line, flush replay loop log lines, flush's conversion of the returned rows into count fields, expiry logging, new context-builder helper.
- `notificationforwarder/src/notificationforwarder/text/logger.py` and `json/logger.py`: new templates / allowlisted fields for every affected line (these are the layers that decide what is rendered to the log target).
- Tests: `tests/test_resilience_spool.py`, `test_delivery_resilience.py`, `test_classes.py`, `test_loggers.py`, `test_logger.py` assertions that pin log content; two unit assertions pin `prune_expired()`'s old int return; one stub returns `spool() → False` where a tuple contract is coming.
- No schema change, no CLI change, no eventhandler change. Log volume grows deliberately (one line per expired event); rotation settings are already in place.
