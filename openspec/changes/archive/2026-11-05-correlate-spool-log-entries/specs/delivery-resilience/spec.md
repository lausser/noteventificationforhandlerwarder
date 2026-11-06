# Spec Delta

## ADDED Requirements

### Requirement: The spool-time log line identifies the spool entry
When a failed delivery causes an event to be spooled, the log line that reports the failed delivery SHALL carry the event id which is identical to the database record id under which the raw event was stored in the spool, the decoded raw event that was passed to the spool (the exact payload stored), and the summary of the formatted event when it has one.

#### Scenario: Spool line carries id and stored payload
- **WHEN** a failed submit for a non-heartbeat event spools the raw event
- **THEN** the "forward failed" log entry carries the id of the newly created spool row and the raw event that was stored, in addition to the formatted event's summary when it exists

#### Scenario: Correlation holds across the spool lifetime when the id never changes
- **WHEN** a spooled event is later replayed and delivered successfully without any move-to-end in between
- **THEN** both the spool-time log entry and the "delete spooled event" log entry carry the same event id

#### Scenario: Correlation survives a move-to-end through the bridge log
- **WHEN** a spooled event is moved to the end of the spool after a failed replay, and is delivered successfully by a later replay
- **THEN** the critical move-to-end bridge line links the old event id of the spool-time log entry to the new event id without carrying event content, and the "delete spooled event" log entry carries the new event id, while the spool-time line and the delete line carry the identical raw event content

### Requirement: Spool removal and rejection log lines carry event id and event content
Every log line that removes a spooled event from the spool during replay, or reports that it stays, shall carry the spool record id, the summary of the formatted event when a summary exists, and the decoded raw event. The id and content SHALL appear in the rendered log output of both the default text logger and the JSON logger: the text logger renders them in its message, and the JSON logger exposes the full decoded raw event as a structured field even when a formatted event is also present.

#### Scenario: Successful replay deletion is self-describing
- **WHEN** a spooled event is replayed and the submit succeeds
- **THEN** the "delete spooled event" log entry in the rendered log output contains the event id, the summary when it exists, and the raw event

#### Scenario: Persistent replay failure is self-describing
- **WHEN** a replayed submit fails and the event stays in the spool
- **THEN** the "event stays in spool" log entry in the rendered log output contains the event id, the summary when it exists, the raw event, and the submit error

#### Scenario: Discard during replay is self-describing
- **WHEN** a spooled event is discarded by the formatter during replay, including a formatter that sets a summary before discarding
- **THEN** the discard log entry in the rendered log output contains the event id, the summary when the formatted event has one, and the decoded raw event

#### Scenario: Unformattable spooled event shows the raw event
- **WHEN** a spooled event cannot be formatted during replay
- **THEN** the "could not format spooled event" and "delete trash event" log entries in the rendered log output contain the event id and the decoded raw event

#### Scenario: Formatter mutations do not alter the logged stored event
- **WHEN** a formatter changes top-level fields or nested dictionaries and lists of a replayed event, including adding a value that cannot be JSON-serialized
- **THEN** replay log entries in both text and JSON output contain the decoded stored payload without those mutations, and successful replay continues to later in-retention rows

### Requirement: Correlation degrades gracefully when no summary exists
The runtime SHALL never invent a summary and shall omit the summary field unless the formatted event exists and has a non-empty summary. When no formatted event exists or its summary is empty, the content is provided by the decoded raw event only.

#### Scenario: Hard formatter failure leaves only the raw event
- **WHEN** a spooled event cannot be formatted during replay, so no formatted event and no summary exist
- **THEN** its log entries carry the decoded raw event and omit the summary instead of carrying fabricated content

#### Scenario: Empty summary on an existing formatted event
- **WHEN** a replayed event has a formatted event without a summary
- **THEN** its log entries omit the summary key and still include the raw event

### Requirement: Expired spool entries are logged individually
When a flush removes spooled events because their retention window has passed, the runtime SHALL log one entry per expired event, at minimum with the spool record id and the decoded raw event, in addition to the existing aggregate count line. Spool entry removal at expiry is decided by the flush, so the per-event entries describe exactly the rows expired in that flush.

#### Scenario: Each expired event is named
- **WHEN** a flush finds three entries past the retention window and removes them
- **THEN** three log entries are emitted, each carrying the event id and the raw event of one expired spool row

#### Scenario: Aggregate count survives
- **WHEN** any expired events were removed
- **THEN** the existing "dropped outdated events" count entry is still logged with an integer count, alongside the per-event entries, and the spool replay summary keeps reporting an integer dropped count

#### Scenario: Undecodable expired payload does not abort the flush
- **WHEN** an expired row's payload cannot be decoded, and other spooled rows are still inside the retention window
- **THEN** the runtime logs that entry's id and its undecodable payload text and continues the flush without skipping the replay of the remaining in-retention rows
