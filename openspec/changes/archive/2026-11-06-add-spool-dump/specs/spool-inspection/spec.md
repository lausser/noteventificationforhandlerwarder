# Spec Delta

## Purpose

Give operators a read-only way to inspect the events a notificationforwarder instance has spooled — which events are stuck, when they were spooled, and their full content — through the existing command, with ordering and limiting, without touching delivery or retry behavior.

## ADDED Requirements

### Requirement: A dump mode is available on the existing notificationforwarder command
The system SHALL provide a dump-spool mode on the existing notificationforwarder command which dumps the spooled events of the forwarder instance selected by the forwarder argument and, optionally, a forwarder tag. The dump SHALL read the same spool database and table that this forwarder and tag use for delivery. In dump mode the forwarder argument SHALL be required, and every outcome, including an empty spool, SHALL name the resolved database path and table on standard error.

#### Scenario: Dumps the spool of the selected forwarder instance
- **WHEN** the command is called with the dump-spool mode, the forwarder argument `webhook`, and the tag `prod`
- **THEN** the dump reads only `$OMD_ROOT/var/tmp/notificationforwarder_webhook_prod_notifications.db`, table `events_webhook_prod`, and no events of other forwarders or tags are shown

#### Scenario: The forwarder argument is required in dump mode
- **WHEN** the command is called with the dump-spool mode and without a forwarder argument
- **THEN** the exit status is non-zero, standard error carries a usage message, standard output carries no record data, and the default forwarder of the regular notification command is not applied

#### Scenario: The tag remains optional
- **WHEN** the command is called with the dump-spool mode, a forwarder, and no tag
- **THEN** the dump reads the spool of the untagged instance of that forwarder

#### Scenario: Invoked with the parameters of a regular notification command
- **WHEN** the command is called with the same parameters as in a Naemon notification command definition plus the dump-spool mode
- **THEN** the spool dump runs and no event is formatted, forwarded, spooled, or reported

#### Scenario: No event attributes required
- **WHEN** the command is called with the dump-spool mode and a forwarder but without any eventopt arguments
- **THEN** the dump runs successfully

#### Scenario: A process outside the OMD environment is rejected
- **WHEN** the process is not in an OMD environment, the same condition the regular notification command rejects
- **THEN** the dump is rejected with a non-zero exit status and is not reported as an empty spool

### Requirement: Spool records are listed oldest first by default and newest first on request
The dump SHALL list spooled records oldest first by default and SHALL accept an order parameter to list them newest first. Records SHALL be ordered by the stored spool timestamp with the record number as tie-break, ascending for oldest first and descending for newest first. The order parameter SHALL accept only `oldest` and `newest`; any other value SHALL be a usage error. The default SHALL be `oldest`.

#### Scenario: Default order is oldest first
- **WHEN** the dump runs on a spool holding several records and no order parameter is given
- **THEN** the records are shown starting with the oldest spool timestamp

#### Scenario: Newest first order on request
- **WHEN** the dump runs with the newest-first order parameter
- **THEN** the records are shown starting with the newest spool timestamp

#### Scenario: Identical spool timestamps tie-broken by record number
- **WHEN** two records carry the same spool timestamp
- **THEN** the oldest-first order shows the lower record number first and the newest-first order shows the higher record number first

#### Scenario: An invalid order value is a usage error
- **WHEN** the order parameter is a value other than `oldest` or `newest`
- **THEN** the exit status is non-zero, standard error carries a usage message, and standard output carries no record data

### Requirement: The number of displayed records can be limited
The dump SHALL accept a limit parameter capping the records displayed, applied after ordering. A given limit SHALL be an integer from 1 to 9223372036854775807; zero, a negative value, a non-integer, and an integer above that bound SHALL be usage errors — non-zero exit, one usage line on standard error naming the limit, no raised exception, and an empty standard output. When the limit is omitted or is at least the snapshot size, all records SHALL be displayed.

#### Scenario: No limit shows all records
- **WHEN** the spool holds records and no limit parameter is given
- **THEN** all records in the snapshot are displayed

#### Scenario: Limit caps the output
- **WHEN** the spool holds more records than the limit
- **THEN** exactly the number of records named by the limit parameter are displayed

#### Scenario: Limit applies after ordering
- **WHEN** the dump runs newest first with a limit smaller than the snapshot size
- **THEN** the most recent records are the ones displayed

#### Scenario: Limit larger than the snapshot
- **WHEN** the snapshot holds 3 records and the limit is 10
- **THEN** all 3 records are displayed

#### Scenario: A zero or negative limit is a usage error
- **WHEN** the dump runs with a limit of zero or a negative limit
- **THEN** the exit status is non-zero, standard error carries a usage message, and standard output carries no record data

#### Scenario: A non-integer limit is a usage error
- **WHEN** the limit is not an integer
- **THEN** the exit status is non-zero, standard error carries a usage message, and standard output carries no record data

#### Scenario: A limit beyond the 64-bit range is a usage error
- **WHEN** the limit is an integer greater than 9223372036854775807
- **THEN** the exit status is non-zero, standard error carries one usage line naming the limit, the process raises no exception, and standard output is empty

### Requirement: Each displayed record shows its number, spool time, and event details
Each displayed record SHALL show its record number, its spool time, and the full content of the stored event. The record number SHALL be the row id as stored in the spool table at the time of the dump. The spool time SHALL be the stored spool timestamp verbatim (`YYYY-MM-DD HH:MM:SS`, UTC) and SHALL NOT be converted to local time or reformatted. The human-facing header SHALL state that the spool time is UTC.

#### Scenario: Record fields are shown
- **WHEN** a record is displayed
- **THEN** its record number, its spool time, and the full stored event content are shown

#### Scenario: The spool time is shown verbatim
- **WHEN** the stored spool timestamp is `2026-11-06 02:14:03`
- **THEN** both the text and the JSON output show `2026-11-06 02:14:03`

#### Scenario: Spool time survives re-insertion after failed replay
- **WHEN** a spooled record is re-inserted at the end of the spool after a failed replay and the dump runs afterwards
- **THEN** the record shows its original spool time, not the re-insertion time

#### Scenario: Record number before a replay move
- **WHEN** a record is dumped before any failed replay has moved it
- **THEN** its record number equals the `event_id` the spool log line `forward failed, spool id ...` carries for that event

#### Scenario: Record number after a replay move
- **WHEN** a record has been re-inserted at the end of the spool by a failed replay and is dumped
- **THEN** the dump shows the new row id named on the move log line, the original id is absent from the dump, and the spool time shown is the original stored timestamp

### Requirement: The dump output format is selectable
The dump SHALL support a human-readable `text` format and a `json` format, with `text` as the default. Any other format value SHALL be a usage error: a non-zero exit status, a message on standard error, and no record data on standard output.

#### Scenario: Default is the text format
- **WHEN** the dump runs without a format parameter
- **THEN** the records are rendered in the human-readable text format

#### Scenario: An invalid format value is a usage error
- **WHEN** the dump runs with a format other than `text` or `json`
- **THEN** the exit status is non-zero, standard error carries a usage message, and standard output carries no record data

### Requirement: Text output carries one physical line per record
In `text` format, standard output SHALL be valid UTF-8 independent of the process locale and SHALL carry exactly one physical line per displayed record. A line ends with one U+000A and contains none of U+000A, U+000D, U+0085, U+2028, or U+2029. Characters UTF-8 can encode SHALL appear as themselves, except U+0085, U+2028, U+2029, and U+D800–U+DFFF, which SHALL be JSON `\u` escapes. A decoded payload emitted with those escapes SHALL keep its value and SHALL NOT be marked undecodable or truncated.

#### Scenario: A record occupies one physical line
- **WHEN** a record with a decodable payload is displayed in text format
- **THEN** standard output carries exactly one line containing the record number, the verbatim spool time, and the compact JSON payload

#### Scenario: Informational lines do not pollute standard output
- **WHEN** the dump runs in either format
- **THEN** the lines with the database path, the table, the order, and the total and shown record counts appear on standard error and standard output carries only record data

### Requirement: JSON output is one parseable array
In `json` format, standard output SHALL be valid UTF-8 independent of the process locale and SHALL be one parseable JSON array with one element per displayed record, each carrying `id` (number), `spooled_at` (the verbatim spool time), and `payload` (the decoded event value). In the array text, characters UTF-8 can encode SHALL appear as themselves, except U+0085, U+2028, U+2029, and U+D800–U+DFFF, which SHALL be JSON `\u` escapes.

#### Scenario: JSON output is parseable on standard output
- **WHEN** the dump runs with the `json` format
- **THEN** standard output is one parseable JSON array with one element per displayed record, and each element carries the keys `id`, `spooled_at`, and `payload`

### Requirement: A corrupt stored record does not abort the dump
If the content of a stored record cannot be decoded, the dump SHALL NOT abort and SHALL list the record with its record number and spool time, counting it toward the limit and the shown count. Its `payload` SHALL be `null` and it SHALL additionally carry `undecodable: true` and `raw_prefix` (the first 120 characters of the stored text, with U+0000–U+001F, U+0085, U+2028, and U+2029 written as JSON escapes), in both `json` and `text` format.

#### Scenario: One corrupt record among decodable records
- **WHEN** the spool holds one record whose content cannot be decoded alongside decodable records and the dump runs
- **THEN** all records are listed, the corrupt one is marked undecodable with its raw prefix, and the dump exits with status zero

#### Scenario: A corrupt payload does not split a text line
- **WHEN** a corrupt stored payload contains newline characters and its first 120 characters also contain U+0085 or U+2028, and the dump runs in text format
- **THEN** the record occupies exactly one line on standard output, its raw prefix carries those code points as JSON escapes, and the record's line contains no raw U+0085, U+2028, or U+2029

#### Scenario: A decodable payload that needs escaping is kept, not marked undecodable
- **WHEN** one stored payload decodes to a value containing U+0085, U+2028, U+2029, or a code point in U+D800–U+DFFF, a later record is ordinary text, and the dump runs in text and in `json`
- **THEN** both records are listed, the status is zero, the first record's payload is the decoded event (`payload` is not null and `undecodable` is absent), those code points appear only as JSON `\u` escapes, and standard output is valid UTF-8

### Requirement: An empty or missing spool database is a healthy outcome
When the spool database file does not exist, or the expected table exists and holds no rows, the dump SHALL report the spool as empty on standard error (naming the path and table) and SHALL exit with status zero. A database error that prevents reading — locked or corrupt file, or a file SQLite opens but lacks the expected table, including a zero-byte file — SHALL be an error with a non-zero exit status. On every usage-error and database-error path, standard output is empty (zero bytes).

#### Scenario: Missing spool database
- **WHEN** the dump runs for a forwarder instance whose spool database file does not exist
- **THEN** standard error reports the spool as empty including the resolved path and table, the `text` format writes no bytes to standard output, the `json` format writes an empty JSON array to standard output, and the status is zero

#### Scenario: Empty spool table
- **WHEN** the dump runs for a forwarder instance whose spool table holds no records
- **THEN** standard error reports the spool as empty including the resolved path and table, the `text` format writes no bytes to standard output, the `json` format writes an empty JSON array to standard output, and the status is zero

#### Scenario: Empty spool in JSON format
- **WHEN** the spool is empty and the dump runs with the `json` format
- **THEN** standard output is an empty JSON array and the status is zero

#### Scenario: A missing expected table is an error
- **WHEN** the spool database file exists but does not contain the expected table
- **THEN** the status is non-zero, standard error names the path and the missing table and is not the empty-spool report, and standard output carries no record data

#### Scenario: Unreadable spool database
- **WHEN** the spool database cannot be read because it is locked or corrupt
- **THEN** the dump reports an error on standard error, standard output carries no record data, and the status is non-zero

### Requirement: Total and listed records describe one snapshot
The listed records and the total count SHALL describe one consistent snapshot of the spool. The total SHALL be the number of records in the snapshot, and the shown count SHALL be the number listed after ordering and limit. A row committed after the snapshot began SHALL be in neither the total nor the list. The standard-error summary — path, table, order, total, shown — SHALL be written before the first record on standard output.

#### Scenario: Total and shown counts describe the snapshot
- **WHEN** the snapshot holds 12 records and the limit is 5
- **THEN** standard error reports total 12 and shown 5, and the 5 listed records are the first 5 of the snapshot in the requested order

#### Scenario: Rows committed after the snapshot are not listed
- **WHEN** a row is committed to the spool after the dump's snapshot began
- **THEN** that row is in neither the total nor the list

#### Scenario: The summary is written before the first record
- **WHEN** the dump lists records
- **THEN** the standard-error summary — path, table, order, total, shown — is written before the first record on standard output

### Requirement: The dump tolerates a concurrent writer within a cap
The dump SHALL NOT take the flush lock and SHALL NOT block indefinitely on a concurrent writer. If the database stays locked for more than 1 second, the dump SHALL take the unreadable-database path: a non-zero exit status and no record data on standard output. A row in the snapshot SHALL be listed even if a later flush deletes it before the process exits.

#### Scenario: A brief concurrent flush does not fail the dump
- **WHEN** another process briefly holds the database write lock while the dump runs
- **THEN** the dump completes within the 1-second cap and lists the snapshot

#### Scenario: A database locked beyond the cap is an error
- **WHEN** the database stays locked for more than 1 second
- **THEN** the dump takes the unreadable-database path with a non-zero exit status and no record data on standard output

#### Scenario: The failure path is bounded
- **WHEN** a writer holds the database lock continuously
- **THEN** the process exits with the unreadable-database status within 2 seconds

#### Scenario: A row deleted after the snapshot is still listed
- **WHEN** a flush deletes a row after the dump's snapshot began but before the process exits
- **THEN** the row is still listed

### Requirement: The dump is strictly read-only
The dump SHALL NOT load or invoke the forwarder, formatter, or reporter modules, SHALL NOT attempt to forward, retry, prune, or move spooled events, SHALL NOT acquire the flush lock, and SHALL NOT delete or modify records. The delivery and retry paths SHALL be unchanged.

#### Scenario: Dump leaves the spool intact
- **WHEN** the dump runs on a non-empty spool
- **THEN** the spool still contains the same records with the same spool times afterwards

#### Scenario: Dump runs without receiver availability
- **WHEN** the destination receiver is unreachable and the dump runs
- **THEN** the dump succeeds without contacting the receiver or loading the forwarder module

#### Scenario: Dump runs without a loadable forwarder module
- **WHEN** the named forwarder module cannot be imported and the dump mode is set
- **THEN** the dump still reads that instance's spool

### Requirement: The dump displays only stored record content
The dump SHALL display only the stored record content. It SHALL NOT add a failure-reason field, SHALL NOT attempt to reconstruct why an event was spooled, SHALL NOT read forwarder options, and SHALL NOT display a computed expiry time. The spool log remains the source for the failure reason, correlated by the record number.

#### Scenario: No failure reason in the output
- **WHEN** a record is displayed
- **THEN** the record carries no failure-reason field and the output does not assert a reason for spooling

#### Scenario: No computed expiry
- **WHEN** a record is displayed
- **THEN** the output carries no expiry time and no retention-based age computed from forwarder options
