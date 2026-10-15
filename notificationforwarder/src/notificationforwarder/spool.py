try:
    import simplejson as json
except ImportError:
    import json
import random
import sqlite3
import threading
import time
import fcntl


class SpoolStore:
    def __init__(self, db_file, table_name):
        self.db_file = db_file
        self.table_name = table_name
        self.connection = None
        self.cursor = None
        self._lock = threading.Lock()

    def open(self):
        self.connection = sqlite3.connect(self.db_file, check_same_thread=False)
        self.cursor = self.connection.cursor()

    def init_db(self):
        sql_create = """CREATE TABLE IF NOT EXISTS """ + self.table_name + """ (
                id INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            )"""
        with self._lock:
            self.cursor.execute(sql_create)
            self.connection.commit()

    def count(self, max_id=None):
        sql_count = "SELECT COUNT(*) FROM " + self.table_name
        params = []
        if max_id is not None:
            sql_count += " WHERE id <= ?"
            params.append(max_id)
        with self._lock:
            self.cursor.execute(sql_count, params)
            return self.cursor.fetchone()[0]

    def enqueue(self, raw_event):
        sql_insert = "INSERT INTO " + self.table_name + "(payload) VALUES (?)"
        with self._lock:
            self.cursor.execute(sql_insert, (json.dumps(raw_event),))
            self.connection.commit()

    def prune_expired(self, max_spool_minutes):
        outdated = int(time.time() - 60 * max_spool_minutes)
        sql_delete = "DELETE FROM " + self.table_name + " WHERE CAST(STRFTIME('%s', timestamp) AS INTEGER) < ?"
        with self._lock:
            self.cursor.execute(sql_delete, (outdated,))
            dropped = self.cursor.rowcount
            # commit immediately, otherwise the implicit transaction keeps
            # the database write-locked for other processes during a flush
            self.connection.commit()
            return dropped

    def max_id(self):
        with self._lock:
            self.cursor.execute("SELECT MAX(id) FROM " + self.table_name)
            return self.cursor.fetchone()[0] or 0

    def fetch_batch(self, limit=10, after_id=0, max_id=None):
        sql_select = "SELECT id, payload FROM " + self.table_name + " WHERE id > ?"
        params = [after_id]
        if max_id is not None:
            sql_select += " AND id <= ?"
            params.append(max_id)
        sql_select += " ORDER BY id LIMIT ?"
        params.append(limit)
        with self._lock:
            self.cursor.execute(sql_select, params)
            return self.cursor.fetchall()

    def delete(self, event_id):
        with self._lock:
            self.cursor.execute("DELETE FROM " + self.table_name + " WHERE id = ?", (event_id,))
            self.connection.commit()

    def move_to_end(self, event_id):
        # re-insert the row behind all others, keeping payload and timestamp,
        # so it still expires on schedule. a row which is gone or already the
        # last one (this includes a reused id) is left alone.
        sql_copy = ("INSERT INTO " + self.table_name + "(payload, timestamp)"
                    " SELECT payload, timestamp FROM " + self.table_name +
                    " WHERE id = ? AND id < (SELECT MAX(id) FROM " + self.table_name + ")")
        with self._lock:
            self.cursor.execute(sql_copy, (event_id,))
            if self.cursor.rowcount != 1:
                self.connection.commit()
                return None
            new_id = self.cursor.lastrowid
            self.cursor.execute("DELETE FROM " + self.table_name + " WHERE id = ?", (event_id,))
            self.connection.commit()
            return new_id

    def decode(self, text):
        return json.loads(text)

    def commit(self):
        with self._lock:
            self.connection.commit()

    def close(self):
        with self._lock:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.commit()
                self.connection.close()


def acquire_lock_with_retry(lock_file, app_logger, max_attempts=3, base_delay=0.1):
    for attempt in range(max_attempts):
        try:
            fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            app_logger.debug("flush lock set", {})
            return True
        except IOError as exc:
            app_logger.debug("flush lock failed", {
                'attempt': attempt + 1,
                'exception': exc,
            })
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                time.sleep(delay)
    return False
