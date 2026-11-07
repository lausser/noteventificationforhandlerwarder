"""
Spool inspection tests for notificationforwarder.

This file covers the --dump-spool read-only path: argument validation,
ordering and limit, text/JSON rendering, corrupt/empty/missing/unreadable
spool handling, the lock cap, CLI integration, and read-only integrity.
"""
import fcntl
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest

os.environ["PYTHONDONTWRITEBYTECODE"] = "true"

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
BIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "notificationforwarder"))
TABLE_SUFFIX = "_notifications.db"


@pytest.fixture
def omd_root(tmp_path, monkeypatch):
    root = tmp_path / "omd"
    (root / "var" / "log").mkdir(parents=True)
    (root / "var" / "tmp").mkdir(parents=True)
    (root / "tmp").mkdir(parents=True)
    monkeypatch.setenv("OMD_ROOT", str(root))
    return root


def _db_file(omd_root, forwarder, tag=None):
    name = forwarder + ("_" + tag if tag else "")
    return str(omd_root / "var" / "tmp" / ("notificationforwarder_" + name + TABLE_SUFFIX))


def _seed(omd_root, forwarder, tag=None, rows=None):
    db = _db_file(omd_root, forwarder, tag)
    table = "events_" + (forwarder + ("_" + tag if tag else ""))
    connection = sqlite3.connect(db)
    cursor = connection.cursor()
    # the quoted table name keeps special characters (e.g. '#') in tags valid
    cursor.execute(
        'CREATE TABLE "' + table + '" ('
        "id INTEGER PRIMARY KEY, payload TEXT NOT NULL, "
        "timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)"
    )
    if rows:
        cursor.executemany(
            'INSERT INTO "' + table + '" (id, payload, timestamp) VALUES (?,?,?)', rows)
    connection.commit()
    connection.close()
    return db, table


def _dump(forwarder, tag=None, order="oldest", limit=None, fmt="text"):
    from notificationforwarder import spool_dump
    out, err = io.StringIO(), io.StringIO()
    status = spool_dump.dump_spool(forwarder, tag, order=order, limit=limit, fmt=fmt, out=out, err=err)
    return status, out.getvalue(), err.getvalue()


def _all_lines(stdout):
    return [line for line in stdout.splitlines() if line.strip()]


# ============================================================================
# 1. Read-only dump core
# ============================================================================

class TestDumpCore:
    def test_reads_correct_table_for_forwarder_and_tag(self, omd_root):
        _seed(omd_root, "webhook", "prod", [(1, '{"HOSTNAME": "srvblub"}', "2026-11-06 08:12:03")])
        _seed(omd_root, "webhook", None, [(1, '{"HOSTNAME": "srvblub"}', "2026-11-06 08:12:03")])
        status, out, err = _dump("webhook", "prod")
        assert status == 0
        assert "events_webhook_prod" in err
        assert 'srvblub' in out
        # the untagged instance must not leak into the tagged dump
        lines = _all_lines(out)
        assert len(lines) == 1

    def test_default_order_is_oldest_first(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (1, '{"n": 1}', "2026-11-06 09:00:00"),
            (2, '{"n": 2}', "2026-11-06 08:00:00"),
            (3, '{"n": 3}', "2026-11-06 07:00:00"),
        ])
        status, out, _ = _dump("webhook")
        assert status == 0
        ids = [line.split()[0] for line in _all_lines(out)]
        assert ids == ["#3", "#2", "#1"]

    def test_newest_first_order(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (1, '{"n": 1}', "2026-11-06 09:00:00"),
            (2, '{"n": 2}', "2026-11-06 08:00:00"),
            (3, '{"n": 3}', "2026-11-06 07:00:00"),
        ])
        status, out, _ = _dump("webhook", order="newest")
        assert status == 0
        ids = [line.split()[0] for line in _all_lines(out)]
        assert ids == ["#1", "#2", "#3"]

    def test_identical_timestamps_tie_breaked_by_id(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (5, '{"n": "a"}', "2026-11-06 08:00:00"),
            (2, '{"n": "b"}', "2026-11-06 08:00:00"),
            (9, '{"n": "c"}', "2026-11-06 08:00:00"),
        ])
        status, out_oldest, _ = _dump("webhook")
        assert [line.split()[0] for line in _all_lines(out_oldest)] == ["#2", "#5", "#9"]
        status, out_newest, _ = _dump("webhook", order="newest")
        assert [line.split()[0] for line in _all_lines(out_newest)] == ["#9", "#5", "#2"]

    def test_limit_caps_rows_after_ordering(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (i, '{"n": %d}' % i, "2026-11-06 08:%02d:00" % i) for i in range(1, 13)
        ])
        status, out, err = _dump("webhook", order="newest", limit=5)
        assert status == 0
        ids = [line.split()[0] for line in _all_lines(out)]
        assert ids == ["#12", "#11", "#10", "#9", "#8"]
        assert "total: 12" in err
        assert "shown: 5" in err

    def test_no_limit_returns_all_rows(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (i, '{"n": %d}' % i, "2026-11-06 08:00:00") for i in range(1, 13)
        ])
        status, out, err = _dump("webhook")
        assert status == 0
        assert len(_all_lines(out)) == 12
        assert "total: 12" in err
        assert "shown: 12" in err

    def test_limit_larger_than_snapshot_shows_all(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (i, '{"n": %d}' % i, "2026-11-06 08:00:00") for i in range(1, 4)
        ])
        status, out, err = _dump("webhook", limit=10)
        assert status == 0
        assert len(_all_lines(out)) == 3
        assert "total: 3" in err
        assert "shown: 3" in err

    def test_total_and_rows_come_from_one_snapshot(self, omd_root):
        # The dump must report total from the same read as the listed rows.
        # A separate unfiltered COUNT taken outside the snapshot would drift
        # while the receiver is down and rows are enqueued concurrently.
        _seed(omd_root, "webhook", rows=[
            (i, '{"n": %d}' % i, "2026-11-06 08:%02d:00" % i) for i in range(1, 13)
        ])
        status, out, err = _dump("webhook", limit=5)
        assert status == 0
        # total reflects the snapshot (12), shown the limited list (5),
        # and the 5 listed rows are the first 5 of the snapshot in order
        assert "total: 12" in err
        assert "shown: 5" in err
        ids = [line.split()[0] for line in _all_lines(out)]
        assert ids == ["#1", "#2", "#3", "#4", "#5"]

    def test_uri_special_characters_in_omd_root_still_select_the_right_file(self, tmp_path, monkeypatch):
        # a '#' in the OMD_ROOT path is a URI fragment character; without
        # percent-encoding the URI the dump would drop mode=ro and open
        # (and create) the file truncated at the '#'
        root = tmp_path / "omd#site"
        for sub in ("var/log", "var/tmp", "tmp"):
            (root / sub).mkdir(parents=True)
        monkeypatch.setenv("OMD_ROOT", str(root))
        _seed(root, "webhook", "prod", [(1, '{"n": 1}', "2026-11-06 08:00:00")])
        status, out, err = _dump("webhook", "prod")
        assert status == 0
        assert "#1" in out
        assert "events_webhook_prod" in err
        # no truncated sibling for the fragment-truncated path: everything
        # before the first '#' is what an unescaped URI would open instead
        assert not os.path.exists(str(root).rsplit("#", 1)[0])

    def test_locked_beyond_cap_is_error_with_no_record_data(self, omd_root):
        db, _ = _seed(omd_root, "webhook", rows=[(1, '{"n": 1}', "2026-11-06 08:00:00")])
        # An EXCLUSIVE writer genuinely blocks the reader; a BEGIN IMMEDIATE
        # (RESERVED) writer does not, so the dump must succeed while a normal
        # flush is mid-transaction (see test_dump_completes_with_flush_lock_held).
        writer = sqlite3.connect(db)
        writer.execute("BEGIN EXCLUSIVE")
        started = time.time()
        try:
            status, out, err = _dump("webhook")
        finally:
            writer.rollback()
            writer.close()
        waited = time.time() - started
        assert status != 0
        assert "locked" in err.lower()
        assert _all_lines(out) == []
        # the cap is 1 s; the wait should not be unbounded
        assert 0.8 < waited < 10


# ============================================================================
# 2. Argument validation and exit discipline
# ============================================================================

class TestArgumentValidation:
    @pytest.mark.parametrize("kwargs", [
        {"forwarder": None},
        {"forwarder": "webhook", "order": "soonest"},
        {"forwarder": "webhook", "limit": 0},
        {"forwarder": "webhook", "limit": -1},
        {"forwarder": "webhook", "limit": 9223372036854775808},
        {"forwarder": "webhook", "limit": True},
        {"forwarder": "webhook", "fmt": "xml"},
    ])
    def test_invalid_arguments_are_usage_errors_with_no_record_data(self, omd_root, kwargs):
        _seed(omd_root, "webhook", rows=[(1, '{"n": 1}', "2026-11-06 08:00:00")])
        forwarder = kwargs.pop("forwarder", "webhook")
        status, out, err = _dump(forwarder, **kwargs)
        assert status != 0
        assert err.strip()
        assert _all_lines(out) == []

    def test_limit_above_64_bit_bound_is_usage_error_naming_the_limit(self, omd_root):
        _seed(omd_root, "webhook", rows=[(1, '{"n": 1}', "2026-11-06 08:00:00")])
        # must not raise, and the single usage line must name the limit
        status, out, err = _dump("webhook", limit=9223372036854775808)
        assert status != 0
        assert "--limit" in err
        assert "9223372036854775808" in err
        assert _all_lines(out) == []

    def test_limit_at_the_bound_is_accepted(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (i, '{"n": %d}' % i, "2026-11-06 08:00:00") for i in range(1, 4)
        ])
        status, out, err = _dump("webhook", limit=9223372036854775807)
        assert status == 0
        assert len(_all_lines(out)) == 3
        assert "shown: 3" in err

    def test_defaults_applied_when_absent(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (1, '{"n": 1}', "2026-11-06 09:00:00"),
            (2, '{"n": 2}', "2026-11-06 08:00:00"),
        ])
        status, out, err = _dump("webhook")
        assert status == 0
        assert "order: oldest" in err
        # text is the default: one line per record on stdout
        assert len(_all_lines(out)) == 2

    def test_no_record_data_on_missing_table(self, omd_root):
        # a file that exists without the expected table is an error, not "empty"
        db = _db_file(omd_root, "orphan")
        with open(db, "w") as handle:
            handle.write("")
        status, out, err = _dump("orphan")
        assert status != 0
        assert "events_orphan" in err
        assert "spool empty" not in err
        assert _all_lines(out) == []

    def test_no_record_data_on_corrupt_file(self, omd_root):
        db = _db_file(omd_root, "corrupt")
        with open(db, "w") as handle:
            handle.write("this is not a sqlite database")
        status, out, err = _dump("corrupt")
        assert status != 0
        assert err.strip()
        assert "spool empty" not in err
        assert _all_lines(out) == []

    def test_no_omd_root_is_an_error(self, omd_root, monkeypatch):
        monkeypatch.delenv("OMD_ROOT")
        status, out, err = _dump("webhook")
        assert status != 0
        assert "spool empty" not in err
        assert _all_lines(out) == []


# ============================================================================
# 3. Record rendering and formats (pinned)
# ============================================================================

class TestRendering:
    def test_corrupt_record_is_marked_and_does_not_abort(self, omd_root):
        corrupt = "x" * 200 + " not json"
        _seed(omd_root, "webhook", rows=[
            (1, '{"n": 1}', "2026-11-06 08:00:00"),
            (2, corrupt, "2026-11-06 08:01:00"),
            (3, '{"n": 3}', "2026-11-06 08:02:00"),
        ])
        status, out, err = _dump("webhook")
        assert status == 0
        lines = _all_lines(out)
        assert len(lines) == 3
        assert "undecodable" in lines[1]
        # 120-char prefix, no more
        assert corrupt[:120] in lines[1]
        assert corrupt[:121] not in lines[1]

    def test_corrupt_record_counted_toward_limit(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (1, "corrupt", "2026-11-06 08:00:00"),
            (2, '{"n": 2}', "2026-11-06 08:01:00"),
        ])
        status, out, err = _dump("webhook", limit=1)
        assert status == 0
        assert len(_all_lines(out)) == 1
        assert "shown: 1" in err

    def test_spool_time_shown_verbatim_in_both_formats(self, omd_root):
        _seed(omd_root, "webhook", rows=[(1, '{"n": 1}', "2026-11-06 02:14:03")])
        status, out_text, _ = _dump("webhook")
        assert status == 0
        assert "2026-11-06 02:14:03" in out_text
        status, out_json, _ = _dump("webhook", fmt="json")
        assert status == 0
        records = json.loads(out_json)
        assert records[0]["spooled_at"] == "2026-11-06 02:14:03"
        assert records[0]["id"] == 1
        assert records[0]["payload"] == {"n": 1}

    def test_text_header_written_to_stderr_before_first_record(self, omd_root):
        _seed(omd_root, "webhook", rows=[(1, '{"n": 1}', "2026-11-06 08:00:00")])
        status, out, err = _dump("webhook")
        assert status == 0
        header = "spool: "
        assert header in err
        assert "total:" in err
        assert "shown:" in err
        assert header not in out
        # the header keys must not appear on the record stream at all
        record_lines = _all_lines(out)
        assert all(not line.startswith(("spool:", "total:", "shown:", "order:", "table:"))
                   for line in record_lines)

    def test_text_one_physical_line_per_record(self, omd_root):
        payload = json.dumps({"HOSTNAME": "srvblub", "SERVICEOUTPUT": "line\nwith\nbreaks"})
        _seed(omd_root, "webhook", rows=[(1, payload, "2026-11-06 08:00:00")])
        status, out, _ = _dump("webhook")
        assert status == 0
        lines = _all_lines(out)
        assert len(lines) == 1
        # the embedded newlines are escaped, so the payload stays on one line
        assert "line\\nwith\\nbreaks" in lines[0]

    def test_text_non_ascii_preserved_as_characters(self, omd_root):
        payload = json.dumps({"HOSTNAME": "srv-blüher"})
        _seed(omd_root, "webhook", rows=[(1, payload, "2026-11-06 08:00:00")])
        status, out, _ = _dump("webhook")
        assert status == 0
        assert "srv-blüher" in out
        assert "\\u00fc" not in out

    def test_decodable_payload_needing_escaping_is_kept_not_undecodable(self, omd_root):
        # U+0085/U+2028 are line breaks JSON can hold; the payload must stay
        # decoded (not undecodable) and appear only as JSON escapes.
        payload = json.dumps({"HOSTNAME": "srvblub", "NOTE": "a\u0085b\u2028c\u2029d"},
                             ensure_ascii=False)
        _seed(omd_root, "webhook", rows=[
            (1, payload, "2026-11-06 08:00:00"),
            (2, '{"n": 2}', "2026-11-06 08:01:00"),
        ])
        status, out, _ = _dump("webhook")
        assert status == 0
        lines = _all_lines(out)
        assert len(lines) == 2
        assert "undecodable" not in lines[0]
        # no raw line breaks on the record line
        assert not any(ch in lines[0] for ch in ("\u0085", "\u2028", "\u2029"))
        assert "\\u0085" in lines[0]
        assert "\\u2028" in lines[0]
        assert "\\u2029" in lines[0]
        # stdout stays valid UTF-8
        out.encode("utf-8")
        # the JSON form carries the decoded value, not a marker
        status, out_json, _ = _dump("webhook", fmt="json")
        assert status == 0
        records = json.loads(out_json)
        assert records[0]["payload"] == {"HOSTNAME": "srvblub", "NOTE": "a\u0085b\u2028c\u2029d"}
        assert "undecodable" not in records[0]

    def test_corrupt_payload_with_line_breaks_stays_one_escaped_line(self, omd_root):
        corrupt = "junk\u0085line2\u2028" + "x" * 200
        _seed(omd_root, "webhook", rows=[
            (1, corrupt, "2026-11-06 08:00:00"),
            (2, '{"n": 2}', "2026-11-06 08:01:00"),
        ])
        status, out, _ = _dump("webhook")
        assert status == 0
        lines = _all_lines(out)
        assert len(lines) == 2
        corrupt_line = lines[0]
        assert "undecodable" in corrupt_line
        # the 120-char prefix carries the line breaks as JSON escapes
        assert corrupt[:120] not in corrupt_line
        assert "\\u0085" in corrupt_line
        assert "\\u2028" in corrupt_line
        assert not any(ch in corrupt_line for ch in ("\u0085", "\u2028", "\u2029"))
        out.encode("utf-8")

    def test_json_output_is_one_parseable_array(self, omd_root):
        _seed(omd_root, "webhook", rows=[
            (1, '{"n": 1}', "2026-11-06 08:00:00"),
            (2, "corrupt", "2026-11-06 08:01:00"),
        ])
        status, out, _ = _dump("webhook", fmt="json")
        assert status == 0
        records = json.loads(out)
        assert isinstance(records, list)
        assert len(records) == 2
        assert set(records[0].keys()) == {"id", "spooled_at", "payload"}
        assert set(records[1].keys()) == {"id", "spooled_at", "payload", "undecodable", "raw_prefix"}
        assert records[1]["payload"] is None
        assert records[1]["undecodable"] is True

    def test_lone_surrogate_escapes_only_surrogates_in_json(self, omd_root):
        # a lone surrogate (U+D800, not UTF-8 encodable) must not push the
        # whole array to \u-escaped non-ASCII: only the surrogates are escaped.
        # The stored payloads are the ASCII-escaped json.dumps form that
        # enqueue() writes; json.loads decodes them back to surrogates.
        _seed(omd_root, "webhook", rows=[
            (1, '{"h": "\\u00fc\\ud800x"}', "2026-11-06 08:00:00"),
            (2, '{"h": "\\u00fcplain"}', "2026-11-06 08:01:00"),
        ])
        status, out, _ = _dump("webhook", fmt="json")
        assert status == 0
        body = out
        # valid UTF-8 on stdout
        body.encode("utf-8")
        records = json.loads(body)
        assert records[0]["payload"] == {"h": "\u00fc\ud800x"}
        assert records[1]["payload"] == {"h": "\u00fcplain"}
        # the clean row's ü stays a character, only the surrogate is escaped
        assert "\u00fcplain" in body
        assert "\\ud800" in body
        # the text form keeps the clean row's ü too
        status, out_text, _ = _dump("webhook")
        assert status == 0
        lines = _all_lines(out_text)
        assert "\u00fcplain" in lines[1]
        assert "\\ud800" in lines[0]
        out_text.encode("utf-8")

    def test_json_empty_spool_is_empty_array(self, omd_root):
        _seed(omd_root, "webhook")
        status, out, err = _dump("webhook", fmt="json")
        assert status == 0
        assert json.loads(out) == []
        assert "spool empty" in err


# ============================================================================
# 4. Empty, missing, and unreadable spool handling
# ============================================================================

class TestEmptyAndUnreadable:
    def test_missing_spool_file_is_healthy_empty(self, omd_root):
        status, out, err = _dump("webhook", "prod")
        assert status == 0
        assert "spool empty" in err
        assert _db_file(omd_root, "webhook", "prod") in err
        assert "events_webhook_prod" in err
        assert _all_lines(out) == []

    def test_empty_spool_table_is_healthy_empty(self, omd_root):
        _seed(omd_root, "webhook")
        status, out, err = _dump("webhook")
        assert status == 0
        assert "spool empty" in err
        assert _db_file(omd_root, "webhook") in err
        assert "events_webhook" in err
        assert _all_lines(out) == []


# ============================================================================
# 5. Read-only guarantee
# ============================================================================

class TestReadOnly:
    def test_dump_does_not_mutate_the_spool(self, omd_root):
        db, table = _seed(omd_root, "webhook", rows=[
            (1, '{"n": 1}', "2026-11-06 08:00:00"),
            (2, '{"n": 2}', "2026-11-06 08:01:00"),
        ])
        before = sqlite3.connect(db).execute("SELECT id, timestamp, payload FROM " + table).fetchall()
        for order in ("oldest", "newest"):
            for fmt in ("text", "json"):
                status, _, _ = _dump("webhook", order=order, fmt=fmt)
                assert status == 0
        after = sqlite3.connect(db).execute("SELECT id, timestamp, payload FROM " + table).fetchall()
        assert before == after

    def test_dump_completes_with_flush_lock_held(self, omd_root):
        _seed(omd_root, "webhook", rows=[(1, '{"n": 1}', "2026-11-06 08:00:00")])
        lock_file = os.path.join(str(omd_root), "tmp", "notificationforwarderwebhook_flush.lock")
        with open(lock_file, "w") as handle:
            fcntl.lockf(handle, fcntl.LOCK_EX)
            try:
                status, out, _ = _dump("webhook")
            finally:
                fcntl.lockf(handle, fcntl.LOCK_UN)
        assert status == 0
        assert "#1" in out

    def test_dump_succeeds_while_a_normal_flush_holds_a_reserved_lock(self, omd_root):
        db, _ = _seed(omd_root, "webhook", rows=[(1, '{"n": 1}', "2026-11-06 08:00:00")])
        # A flush takes BEGIN IMMEDIATE (a RESERVED lock) for its prune step.
        # A read must not block on that; only an exclusive writer (the cap
        # path) makes the dump fail.
        writer = sqlite3.connect(db)
        writer.execute("BEGIN IMMEDIATE")
        started = time.time()
        try:
            status, out, _ = _dump("webhook")
        finally:
            writer.rollback()
            writer.close()
        assert status == 0
        assert "#1" in out
        assert time.time() - started < 0.5

    def test_no_reason_or_expiry_fields_in_output(self, omd_root):
        _seed(omd_root, "webhook", rows=[(1, '{"n": 1}', "2026-11-06 08:00:00")])
        status, out, err = _dump("webhook")
        assert status == 0
        # the stderr summary carries only the fixed header fields, none of
        # which is a failure reason or a computed expiry
        header_lines = [line for line in err.splitlines() if line.strip()]
        assert header_lines
        assert all(line.split(":")[0].strip() in ("spool", "table", "order", "total", "shown")
                   for line in header_lines)
        # the record stream carries only record number, spool time, payload
        assert all(line.startswith("#1") for line in _all_lines(out))
        status, out_json, _ = _dump("webhook", fmt="json")
        records = json.loads(out_json)
        for record in records:
            for key in record:
                assert "reason" not in key
                assert "expir" not in key


# ============================================================================
# 6. CLI integration
# ============================================================================

class TestCLI:
    @pytest.fixture
    def cli_env(self, omd_root):
        env = os.environ.copy()
        env["OMD_ROOT"] = str(omd_root)
        env["OMD_SITE"] = "my_devel_site"
        pythonpath = env.get("PYTHONPATH", "")
        if SRC not in pythonpath:
            pythonpath = SRC + (":" + pythonpath if pythonpath else "")
        env["PYTHONPATH"] = pythonpath
        return env

    def _run(self, env, *args):
        return subprocess.run(
            [sys.executable, BIN, *args],
            capture_output=True, text=True, env=env,
        )

    def test_cli_dump_text(self, omd_root, cli_env):
        _seed(omd_root, "webhook", "prod", [(1, '{"HOSTNAME": "srvblub"}', "2026-11-06 08:12:03")])
        result = self._run(cli_env, "--forwarder", "webhook", "--forwardertag", "prod", "--dump-spool")
        assert result.returncode == 0
        assert "#1" in result.stdout
        assert "spool:" in result.stderr
        assert "total: 1" in result.stderr

    def test_cli_dump_json_parses(self, omd_root, cli_env):
        _seed(omd_root, "webhook", "prod", [(1, '{"HOSTNAME": "srvblub"}', "2026-11-06 08:12:03")])
        result = self._run(cli_env, "--forwarder", "webhook", "--forwardertag", "prod",
                           "--dump-spool", "--dump-format", "json")
        assert result.returncode == 0
        records = json.loads(result.stdout)
        assert records[0]["id"] == 1
        assert records[0]["payload"] == {"HOSTNAME": "srvblub"}

    def test_cli_dump_requires_forwarder(self, omd_root, cli_env):
        result = self._run(cli_env, "--dump-spool")
        assert result.returncode != 0
        assert "--forwarder" in result.stderr
        assert result.stdout == ""

    @pytest.mark.parametrize("bad_limit", ["abc", "0", "-3", str(9223372036854775808)])
    def test_cli_dump_invalid_limit_is_usage_error(self, omd_root, cli_env, bad_limit):
        _seed(omd_root, "webhook", "prod", [(1, '{"HOSTNAME": "srvblub"}', "2026-11-06 08:12:03")])
        result = self._run(cli_env, "--forwarder", "webhook", "--forwardertag", "prod",
                           "--dump-spool", "--limit", bad_limit)
        assert result.returncode != 0
        assert "--limit" in result.stderr
        assert bad_limit in result.stderr
        # the spec pins one usage line naming the limit
        assert len([line for line in result.stderr.splitlines() if line.strip()]) == 1
        assert result.stdout == ""

    def test_cli_dump_with_notification_command_parameters(self, omd_root, cli_env):
        _seed(omd_root, "webhook", "prod", [(1, '{"HOSTNAME": "srvblub"}', "2026-11-06 08:12:03")])
        result = self._run(cli_env,
                           "--forwarder", "webhook", "--forwardertag", "prod",
                           "--eventopt", "HOSTNAME=srvblub", "--eventopt", "SERVICESTATE=CRITICAL",
                           "--dump-spool", "--order", "newest", "--limit", "5")
        assert result.returncode == 0
        assert "#1" in result.stdout

    def test_cli_dump_does_not_forward(self, omd_root, cli_env):
        # a dump must not run the pipeline: no new rows appear in the spool
        db, table = _seed(omd_root, "webhook", "prod", [(1, '{"HOSTNAME": "srvblub"}', "2026-11-06 08:12:03")])
        result = self._run(cli_env, "--forwarder", "webhook", "--forwardertag", "prod",
                           "--eventopt", "HOSTNAME=srvblub", "--dump-spool")
        assert result.returncode == 0
        count = sqlite3.connect(db).execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
        assert count == 1

    def test_cli_dump_without_forwarder_module(self, omd_root, cli_env):
        # the spool is read directly, so a forwarder that cannot be imported
        # must not prevent the dump
        _seed(omd_root, "nosuchforwarder", rows=[(1, '{"HOSTNAME": "srvblub"}', "2026-11-06 08:12:03")])
        result = self._run(cli_env, "--forwarder", "nosuchforwarder", "--dump-spool")
        assert result.returncode == 0
        assert "#1" in result.stdout

    def test_cli_dump_missing_spool_is_healthy(self, omd_root, cli_env):
        result = self._run(cli_env, "--forwarder", "webhook", "--dump-spool")
        assert result.returncode == 0
        assert "spool empty" in result.stderr
        assert result.stdout == ""

    def test_cli_dump_locked_db_is_error(self, omd_root, cli_env):
        db, _ = _seed(omd_root, "webhook", rows=[(1, '{"n": 1}', "2026-11-06 08:00:00")])
        writer = sqlite3.connect(db)
        # EXCLUSIVE, not IMMEDIATE: only an exclusive writer blocks the read.
        writer.execute("BEGIN EXCLUSIVE")
        try:
            result = self._run(cli_env, "--forwarder", "webhook", "--dump-spool")
        finally:
            writer.rollback()
            writer.close()
        assert result.returncode != 0
        assert result.stdout == ""
        assert "locked" in result.stderr.lower()

    def test_cli_dump_outside_omd_environment_is_rejected(self, omd_root):
        env = os.environ.copy()
        env.pop("OMD_ROOT", None)
        env.pop("OMD_SITE", None)
        pythonpath = env.get("PYTHONPATH", "")
        if SRC not in pythonpath:
            pythonpath = SRC + (":" + pythonpath if pythonpath else "")
        env["PYTHONPATH"] = pythonpath
        result = subprocess.run([sys.executable, BIN, "--forwarder", "webhook", "--dump-spool"],
                                capture_output=True, text=True, env=env)
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "spool empty" not in combined

    def test_cli_normal_mode_defaults_to_syslog(self, omd_root, cli_env):
        # regression: outside dump mode the syslog default still applies
        result = self._run(cli_env, "--eventopt", "HOSTNAME=srvblub")
        assert result.returncode == 0
