# Design

## Context

See proposal.md - Why. Current state that shapes the approach:

- `SpoolStore.enqueue()` (spool.py:44-48) inserts the row but does not capture `cursor.lastrowid`; the id evaporates after the INSERT statement.
- `spool()` (baseclass.py:401-415) returns a bare `True`, consumed by `forward()` (baseclass.py:272) in production; two tests also call or stub it (`test_spool_init_failure_returns_false` asserts a bare `False`, test_delivery_resilience.py stubs `spool` as `lambda raw_event: False`).
- The flush replay loop (baseclass.py:475-534) logs `event_id` for every decision it makes about a row, but the event content (summary / decoded raw event) only appears in the "could not format" line.
- Context dicts do NOT reach the log target by themselves. Both shipped loggers are rendering layers that decide what is printed: the text logger turns a context into a fixed message per named line/action (text/logger.py:56-118; the `delete spooled event {id}` template is exactly the line the user complained about; `stays_in_spool` and `delete_trash` have templates but the live contexts omit `spooled_count`, so they fall through to a message without the id; "discard spooled event during replay" has no template). The JSON logger is a key allowlist (json/logger.py:66-176): no `summary` key is copied, and `raw_event` is only read in the `elif` branch when no `formatted_event` is present (json/logger.py:67-72), then reduced to a handful of Naemon keys by `_add_raw_event_info` (json/logger.py:209-232). Adding fields to context dicts alone is therefore not sufficient.
- `prune_expired()` (spool.py:50-59) bulk-deletes expired rows and returns only `cursor.rowcount`; `dropped` is consumed as an int by the aggregate log line (baseclass.py:463-465), the replay summary (`dropped_count`, baseclass.py:548), and two unit assertions that pin the int (`test_resilience_spool.py:1000, 1197-1198`). It commits inside the lock immediately (see tasks/todo.md: write-lock brevity is a deliberate behavior).
- `move_to_end()` (spool.py:83-98) already assigns a spooled event a new id when a flush stopped at it; the baseclass logs both old and new id (baseclass.py:438-442). That bridge line is complete and stays untouched.
- Log volume: default logger is text (baseclass.py:35), rotation is 20MB x3 (util.py, runtime_config.py).

## Goals / Non-Goals

**Goals:**

- Every spool-related log line is a closed information loop: id AND content in the same rendered record — with both the default text logger and the JSON logger — so any single pasted line answers "which event was this".
- Correlation survives from spool time to delete time: via the id when no move intervened, and walkable through the move-to-end bridge line when a move happened; and via summary/raw event content without needing the id at all.
- Consistent degradation when a summary cannot exist (formatter exploded mid-replay): the summary field is omitted unless the formatted event has a non-empty summary; the raw event always carries the content; content is never fabricated.

**Non-Goals:**

- No schema change (no AUTOINCREMENT, no new columns). Rowid semantics are accepted; each rendered line carries the raw event, so id ambiguity cannot leave an event unidentifiable even if ids are reused.
- No per-row logging in `count()`, `fetch_batch()`, or lock acquisition; only the specified lines change.
- No change to the move-to-end log line's content (old id + new id is the agreed "cherry"; it stays content-free).
- No change to eventhandler (it has no spool).
- No change to aggregate "spool replay summary" and "spooling queue length" lines beyond the integer-count fix required by the prune return-shape change.

## Decisions

**D1: `enqueue()` returns `lastrowid` (captured inside the store's lock); `spool()` returns `(True, event_id)` / `(False, None)`.**
The production caller at baseclass.py:272 unpacks the tuple; the two tests that call or stub `spool()` are updated in the same task. `lastrowid` is captured inside the `with self._lock` block before any other thread's INSERT can overwrite it on the shared cursor (a SELECT does not clobber it, verified by the partner's local run). Returned tuples truthiness traps are avoided by using only the unpacked success flag. Alternative considered: `spool()` itself logging the id into a new line — rejected because the id belongs in the existing content-bearing "forward failed" line. Logging stays in the baseclass; SpoolStore has no logger.

**D2: One context-builder helper in baseclass, e.g. `spool_event_context(event_id, formatted_event, raw_event)`.**
Injects `event_id`, `summary` (only when a formatted event exists and has a non-empty summary — otherwise the key is omitted entirely), `raw_event` (always, decoded), and `formatted_event` (when it exists). Used for the flush-mode lines and the per-expiry lines; `forward()`'s spool-time context combines the same helper fields with the existing `formatted_event`. The summary omission is pinned here (resolves the former open question); no None-key-variant is kept. Alternative considered: inlining dict construction per call site — rejected as drift-prone; consistent degradation is the point.

**D3: "Summary when it exists, raw event always" degradation.**
Hard formatter failure (`formatted_event is None`) means no summary object exists — the line then carries `raw_event`, which is the pre-format truth anyway (for "could not format" it is exactly what poisoned the formatter). An existing formatted event with an empty summary behaves identically: no fabricated summary. The current flush loop does not run `is_complete()`, so empty summaries can genuinely reach the delete lines; the builder tolerates this.

**D4: `prune_expired()` SELECTS the expired rows, then DELETEs, then commits once — all inside its lock — and returns the list of `(id, payload)` tuples.**
`flush()` immediately normalizes to an integer: `dropped_rows = prune_expired()`, `dropped = len(dropped_rows)`, and both the aggregate line and the replay summary keep receiving that int, so all existing count consumers stay int-typed. Per-event decoding and logging happen after the return, outside the SQLite write lock; the entries describe exactly the rows this call deleted (no second read of the table). SELECT and DELETE are one atomic step inside the lock — no commit in between. The immediate-commit behavior from the existing "does not block concurrent spooling" requirement is preserved. Decoding of each expired row is wrapped per-row: an undecodable payload is logged with its id and payload text, and the flush continues — replay of in-retention rows must not be skipped because one expired row is corrupt (replay decodes inside the flush try-block, so letting corrupt rows propagate would abort the live replay).

**D5: Leave "delivery failed and event could not be persisted" unchanged.**
When spooling itself fails there is no row and therefore no id; the line already logs the raw event.

**D6: Log-volume growth is accepted for expiry lines.**
User decision: "output every single outdated event's summary and raw data". Worst case is an outage-sized spool mountain expiring together — thousands of full-payload lines into the rotating handler (20MB, 3 backups). Accepted deliberately; no rate limiting.

**D7: The text logger and the JSON logger are extended for every affected line.**
This is where the review's hardest blocker lands: context fields are useless if the rendering layer drops them. (a) Text logger: the action templates gain the id, the summary when it is a non-empty string, and the decoded raw event; `stays_in_spool` / `delete_trash` either get the missing `spooled_count` in their contexts or their template branch condition is relaxed; "discard spooled event during replay" gets a template; the "forward failed" spool-time template gains id and raw event. (b) JSON logger: the allowlist copies `summary` when present, and the full decoded raw event is exposed as a structured field even when `formatted_event` is also present (today `raw_event` only survives the `elif` branch). Verification asserts the rendered output — text lines and JSON entries — not the context dicts.

**D8: Decode each replayed spool payload twice before formatting.**
Call the existing `SpoolStore.decode(text)` twice on the fetched row: retain one decoded value for every replay log context and pass the other to `format_event()`. Formatters and forwarders can mutate event options, including nested dictionaries and lists; a shallow copy would share those nested values. Separate decoding preserves the stored content without a second database read or a duplicate decoder implementation. It adds one JSON parse per replayed event. Expiry logging does not format the event and needs only one decode.

## Risks / Trade-offs

- [Id churn by `move_to_end()`] → The id in the spool-time line later changes. Mitigation: the critical "spooled event moved to the end of the spool" bridge log links the old id to the new id and stays content-free (Non-Goal); the raw event matches byte for byte on the spool-time line and the delete line, so content correlation never depends on id walking alone.
- [Rowid reuse] → Without AUTOINCREMENT SQLite can hand a freshly inserted row the id of a previously deleted row when the deleted row is the maximum id at delete time. The bridge log covers move-to-end renumbering, not this reuse. Accepted as a Non-Goal (no schema change); because every rendered line also carries the full raw event, a reused id can never strip an event of its identity — the id is a convenience, the payload is the proof.
- [Log volume from per-event expiry lines] → Accepted deliberately (D6); rotation is in place, and this mirrors the existing user preference that "adding more content to a log line is not a problem".
- [Existing tests pin rendered log text and context shapes] → `test_delivery_resilience.py` pins the exact text "delete spooled event {id}"; several tests assert context/spool shapes. New fields are additive, but template changes change rendered text; assertion updates are part of the tasks, and pinning tests assert rendered output for both loggers rather than context dicts.
- [`spool()` tuple return change] → Guarded by updating the production caller and the two test call sites in the same task; a new unit test pins the `(success, event_id)` contract so future callers cannot mistake the old shape.
- [JSON raw-event duplication] → Log entries carrying both the formatted event fields and the full raw dict roughly double the fields per spool-related line. Deliberate: the raw event is the stored payload and the only content that exists in degradation cases.

## Migration Plan

Deploy-and-run change, no data migration: spool database schema is untouched, existing spooled rows gain their fields as before the change and are flushed/dropped exactly like before. Log consumers see additional rendered text on existing lines and additional JSON fields; anything keying on the existing fields/message prefixes keeps working (rendered text keeps the same message lead; new content follows). Rollback is a plain revert.

## Open Questions

None. The former open question (summary key None-vs-omitted) is resolved by D2: omit unless non-empty.
