"""Read-only inspection of a notificationforwarder spool database.

This is a pure read path. It resolves the spool database and table from the
forwarder name and an optional tag, opens them read-only, and prints the spooled
records. It never loads a forwarder, formatter, or reporter module, never takes
the flush lock, and never modifies the spool.

The failure reason for a spooled event is not stored in the database, so this
module does not derive or display one; the spool log remains the source,
correlated by the record number.
"""
import json
import os
import re
import sqlite3
import sys
from urllib.parse import quote

# Cap on how long the dump waits on a concurrent writer before failing.
LOCK_TIMEOUT_MS = 1000
# How many characters of a corrupt payload to show so the operator has a breadcrumb.
RAW_PREFIX_LENGTH = 120
# Upper bound for --limit; a larger value is a usage error.
LIMIT_MAX = 9223372036854775807


def _forwarder_name(forwarder, tag):
    return forwarder + ("_" + tag if tag else "")


def _use_utf8(stream):
    # stdout and stderr carry valid UTF-8 independent of the process locale
    # (e.g. LC_ALL=C with locale coercion disabled).
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass


def _spool_paths(forwarder, tag):
    forwarder_name = _forwarder_name(forwarder, tag)
    omd_root = os.environ.get("OMD_ROOT", "")
    # Absolute so the read-only URI connect below is valid and the reported
    # path is unambiguous.
    db_file = os.path.abspath(omd_root + "/var/tmp/notificationforwarder_"
                             + forwarder_name + "_notifications.db")
    table = "events_" + forwarder_name
    return db_file, table


def _decode_payload(text):
    """Return (decodable, value, prefix).

    On success, (True, decoded_value, None). On failure, (False, None, prefix)
    where prefix is the first RAW_PREFIX_LENGTH characters of the stored text.
    """
    try:
        return True, json.loads(text), None
    except (ValueError, TypeError):
        if isinstance(text, str):
            prefix = text[:RAW_PREFIX_LENGTH]
        else:
            prefix = str(text)[:RAW_PREFIX_LENGTH]
        return False, None, prefix


def _spool_time(value):
    # Show the stored timestamp verbatim (UTC YYYY-MM-DD HH:MM:SS). No conversion.
    return str(value)


def _header(err, order, db_file, table, total, shown):
    # Header to stderr before the first record so an interrupted dump still
    # shows the counts, and the spool time is labeled UTC.
    err.write("spool: {}\n".format(db_file))
    err.write("table: {}\n".format(table))
    err.write("order: {} (spool time UTC)\n".format(order))
    err.write("total: {}\n".format(total))
    err.write("shown: {}\n".format(shown))


def _write_empty(err, out, fmt, db_file, table, order):
    _header(err, order, db_file, table, 0, 0)
    err.write("spool empty\n")
    if fmt == "json":
        out.write("[]\n")


# U+0085 (NEL), U+2028, U+2029 are line breaks that json.dumps with
# ensure_ascii=False leaves raw; escape them so one record stays one
# physical line and stdout stays valid UTF-8 independent of the locale.
_LINE_BREAKS = re.compile("[\u0085\u2028\u2029]")


def _escape_line_breaks(text):
    return _LINE_BREAKS.sub(lambda match: "\\u{:04x}".format(ord(match.group(0))), text)


# Lone surrogates (U+D800-U+DFFF) cannot be encoded in UTF-8; JSON carries
# them only as \u escapes, so escape exactly those code points and leave
# every other character (including all other non-ASCII) as itself.
_SURROGATES = re.compile("[\ud800-\udfff]")


def _escape_surrogates(text):
    return _SURROGATES.sub(lambda match: "\\u{:04x}".format(ord(match.group(0))), text)


def _encode_utf8(value):
    """Return a UTF-8-encodable JSON string for value.

    ensure_ascii=False keeps non-ASCII readable; line breaks and lone
    surrogates are escaped so the result stays one line and valid UTF-8.
    Returns None when the value cannot be JSON encoded at all.
    """
    try:
        text = _escape_line_breaks(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return None
    text = _escape_surrogates(text)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return text


def _render(rows, total, order, fmt, db_file, table, out, err):
    shown = len(rows)
    _header(err, order, db_file, table, total, shown)

    if fmt == "json":
        elements = []
        for row_id, ts, payload_text in rows:
            decodable, value, prefix = _decode_payload(payload_text)
            record = {"id": row_id, "spooled_at": _spool_time(ts)}
            if decodable:
                encoded = _encode_utf8(value)
                if encoded is None:
                    record["payload"] = None
                    record["undecodable"] = True
                    record["raw_prefix"] = prefix
                else:
                    record["payload"] = value
            else:
                record["payload"] = None
                record["undecodable"] = True
                record["raw_prefix"] = prefix
            elements.append(record)
        # ensure_ascii=False keeps non-ASCII readable; line breaks and lone
        # surrogates are escaped so the array stays valid UTF-8.
        body = _escape_surrogates(_escape_line_breaks(json.dumps(elements, ensure_ascii=False)))
        try:
            body.encode("utf-8")
        except UnicodeEncodeError:
            # defensive; escaping the surrogates should already be enough
            body = _escape_line_breaks(json.dumps(elements, ensure_ascii=True))
        out.write(body)
        out.write("\n")
    else:
        for row_id, ts, payload_text in rows:
            decodable, value, prefix = _decode_payload(payload_text)
            body = None
            if decodable:
                body = _encode_utf8(value)
            if body is None:
                # Undecodable or unencodable: marker plus raw prefix, escaped
                # so the record stays one physical line and valid UTF-8.
                prefix_body = _encode_utf8(prefix)
                if prefix_body is None:
                    prefix_body = json.dumps(prefix, ensure_ascii=True)
                body = "[undecodable payload] {}".format(prefix_body)
            out.write("#{}  {}  {}\n".format(row_id, _spool_time(ts), body))
    return 0


def dump_spool(forwarder, tag=None, order="oldest", limit=None, fmt="text", out=None, err=None):
    """Dump the spooled events of one forwarder instance. Returns a process exit code."""
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    _use_utf8(out)
    _use_utf8(err)

    # Argument validation: a violation is a usage error (non-zero, no record data).
    if not forwarder:
        err.write("error: --dump-spool requires --forwarder (or --receiver); "
                  "the syslog default is not applied\n")
        return 2
    if order not in ("oldest", "newest"):
        err.write("error: --order must be 'oldest' or 'newest'\n")
        return 2
    if fmt not in ("text", "json"):
        err.write("error: --dump-format must be 'text' or 'json'\n")
        return 2
    if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool)
                              or limit < 1 or limit > LIMIT_MAX):
        err.write("error: --limit must be an integer between 1 and {} (got {})\n".format(
            LIMIT_MAX, limit))
        return 2

    omd_root = os.environ.get("OMD_ROOT", "")
    if not omd_root:
        err.write("error: OMD_ROOT is not set; cannot resolve the spool database\n")
        return 1

    db_file, table = _spool_paths(forwarder, tag)

    # A missing spool file is a healthy empty spool, not an error.
    if not os.path.exists(db_file):
        _write_empty(err, out, fmt, db_file, table, order)
        return 0

    direction = "ASC" if order == "oldest" else "DESC"

    # Percent-encode the path: an unescaped '#' or '?' in a file or
    # directory name would become a URI fragment/query and drop mode=ro.
    try:
        connection = sqlite3.connect("file:{}?mode=ro".format(quote(db_file, safe="/")), uri=True,
                                     timeout=LOCK_TIMEOUT_MS / 1000.0, isolation_level=None)
    except sqlite3.Error as exc:
        err.write("error: could not open spool database {}: {}\n".format(db_file, exc))
        return 1

    total = 0
    rows = []
    try:
        # One deferred read transaction holds the snapshot across COUNT and
        # SELECT so total and the listed rows describe the same data.
        connection.execute("BEGIN")
        total = connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
        sql = "SELECT id, timestamp, payload FROM {} ORDER BY timestamp {}, id {}".format(
            table, direction, direction)
        params = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = connection.execute(sql, params).fetchall()
        connection.execute("COMMIT")
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if "no such table" in message:
            err.write("error: spool database {} exists but table {} is missing\n".format(db_file, table))
        elif "locked" in message:
            err.write("error: spool database {} stayed locked beyond {} ms: {}\n".format(
                db_file, LOCK_TIMEOUT_MS, exc))
        else:
            err.write("error: could not read spool database {}: {}\n".format(db_file, exc))
        return 1
    except sqlite3.Error as exc:
        err.write("error: could not read spool database {}: {}\n".format(db_file, exc))
        return 1
    finally:
        connection.close()

    if total == 0:
        _write_empty(err, out, fmt, db_file, table, order)
        return 0

    return _render(rows, total, order, fmt, db_file, table, out, err)
