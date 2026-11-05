# Tasks

## 1. Spool store plumbing

- [x] 1.1 `spool.py`: make `enqueue()` return `cursor.lastrowid`, captured inside the `with self._lock` block; verify with a pytest that `SpoolStore.enqueue()` returns the row id matching `SELECT MAX(id)` after insert (`tests/test_resilience_spool.py`, following the resilience-layer conventions)
- [x] 1.2 `spool.py` + `baseclass.py`: change `prune_expired()` to SELECT the expired rows (`id`, `payload`) before DELETE, DELETE and commit once inside the same lock block (no commit between SELECT and DELETE), and return the list of `(id, payload)` tuples; in `flush()` immediately normalize with `dropped = len(rows)` so the "dropped outdated events" line and the replay summary's `dropped_count` stay integers; update the two int-return assertions in `tests/test_resilience_spool.py` (~:1000, ~:1197) accordingly; verify that the prune lock/concurrency tests (`test_resilience_spool.py` lock-duration and "spool while flush replays after prune") pass unmodified

## 2. Spool-time correlation

- [x] 2.1 `baseclass.py`: change `spool()` to return `(True, event_id)` on success and `(False, None)` on database error; update `forward()` to unpack the tuple, and update the two existing `spool()` call-site tests (`test_spool_init_failure_returns_false` asserting the bare `False` result, and the `lambda raw_event: False` stub in `test_delivery_resilience.py`) to the tuple contract, plus add a unit test that pins the `(success, event_id)` return contract; verify all three pass
- [x] 2.2 `baseclass.py` `forward()`: build the spooled "forward failed" context from the event fields (id of the new row, the raw event passed to the spool — the exact stored payload — and the formatted event for summary/exception); verify via rendered-output assertions that both the default text logger and the JSON logger produce a line containing the id, the raw event, and the summary when it exists
- [x] 2.3 Add correlation tests: (a) no-move path — spool a failing event, then flush it to success, assert spool line and delete line share the same `event_id`; (b) move path — reproduce the move-to-end, assert the bridge line links old id to new id and stays content-free, the delete line carries the new id, and the spool-time line and the delete line carry the identical raw event (both shipped-module and own-module forwarder paths, per the resilience test-layer requirement)

## 3. Replay-time content in contexts

- [x] 3.1 `baseclass.py`: add the `spool_event_context(event_id, formatted_event, raw_event)` helper implementing "summary only when the formatted event has a non-empty summary (key omitted otherwise), raw event always, formatted event when it exists"; verify with a unit test covering the three shapes (formatted event with summary, formatted event without summary, formatted event None)
- [x] 3.2 `baseclass.py` flush loop: enrich "delete spooled event", "event stays in spool", "discard spooled event during replay", "could not format spooled event", and "delete trash event" with the context builder; verify each of the five log lines carries id plus content via JSON-logger assertions in the resilience test file, including the summary on the discard line for a formatter that sets a summary before discarding
- [x] 3.3 Add the no-summary degradation tests: assert the omits-the-summary-key behavior on the "could not format spooled event" line and on a replayed event whose formatter left the summary empty (raw event present in both)
- [x] 3.4 Preserve the stored replay payload independently of formatter and forwarder mutations: decode each fetched row twice using `SpoolStore.decode()`, retain one decoded value for every replay log context and pass the other to `format_event()`; test text and JSON rendering when a formatter mutates top-level fields, nested dictionaries and lists, and adds a non-JSON value, and verify successful replay continues to a later in-retention row; rerun the full notificationforwarder test suite

## 4. Log rendering (text + JSON loggers)

- [x] 4.1 `text/logger.py`: extend the rendering for every affected line — the "forward failed" spool-time template (id, decoded raw event, summary when non-empty), the action templates for `delete`, `stays_in_spool` (fix the missing `spooled_count` in the live context so the template fires, or relax the template condition), `delete_trash`, `could_not_format`, and a new template for "discard spooled event during replay"; verify by asserting the rendered text of each line from a text logger end to end
- [x] 4.2 `json/logger.py`: allowlist the new fields — `event_id` (already copied), `summary` when present, and the full decoded raw event exposed as a structured field even when `formatted_event` is also present (do not route it through the present `_add_raw_event_info` Naemon-key reduction); verify by asserting the rendered JSON entries for each affected line contain the full raw dict

## 5. Per-event expiry logging

- [x] 5.1 `baseclass.py` flush: after `prune_expired()` returns rows, decode each expired row and log one line per expired event (id, raw event, no summary key), keeping the aggregate "dropped outdated events" integer count line; wrap each row's decode per try-row so an undecodable payload is logged with its id and payload text and the flush continues instead of aborting; add a test that N decoded expired rows produce N per-event lines plus the count line, and one that a corrupt expired payload does not stop the replay of in-retention rows

## 6. Integration checks

- [x] 6.1 Run the full notificationforwarder test suite (`pytest tests/ -v`) and fix remaining log-content assertion collisions in `test_classes.py`, `test_loggers.py`, `test_logger.py`, `test_delivery_resilience.py` (including the exact-text pin "delete spooled event {id}"), `test_remedy_heartbeat_flow.py`; verify suite green
- [ ] 6.2 Run `flake8 src/notificationforwarder/ --max-line-length=120`; verify clean
- [x] 6.3 Document the correlated fields in the "Spool Flushing" section of `README.md` (~:499) and `INDEX.md` (~:445) — which lines carry id, summary, raw event, in both text and JSON form — and verify the documented behavior matches the tests by cross-checking one rendered text line and one rendered JSON line against the spec scenarios
