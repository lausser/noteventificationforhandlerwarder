from abc import ABCMeta, abstractmethod
from importlib import import_module
import os
import socket
import traceback
import signal
from functools import wraps
import errno
import fcntl
import time
try:
    import simplejson as json
except ImportError:
    import json
import sqlite3

MAXAGE = 5

def timeout(seconds,error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum,frame):
            logger.critical("submit ran into a timeout")
            raise Exception(error_message)

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM,_handle_timeout)
            signal.setitimer(signal.ITIMER_REAL,seconds)
            try: result = func(*args,**kwargs)
            finally: signal.alarm(0)
            return result

        return wraps(func)(wrapper)

    return decorator


class NotificationForwarder(object):
    __metaclass__ = ABCMeta # replace with ...BaseClass(metaclass=ABCMeta):

    def __init__(self, opts):
        self.queued_events = []
        self.max_queue_length = 10
        self.sleep_after_flush = 0
        self.baseclass_logs_summary = True
        for opt in opts:
            setattr(self, opt, opts[opt])

    def init_queue(self, maxlength=10, sleepttime=0):
        self.max_queue_length = maxlength
        self.sleep_after_flush = sleepttime

    def flush_queue(self):
        if not getattr(self, "can_queue", False):
            logger.critical("forwarder {} can not flush_queue events".format(self.__class__.__name__.lower()))
            return
        logger.debug("flush remaining {}".format(len(self.queued_events)))
        if self.queued_events:
            formatted_squashed_event = self.squash_queued_events()
            logger.debug("merge {} queued events and flush".format(len(self.queued_events)))
            self.forward_formatted(formatted_squashed_event)
            self.queued_events = []
            time.sleep(self.sleep_after_flush)


    def forward_queued(self, raw_event):
        if not getattr(self, "can_queue", False):
            logger.critical("forwarder {} can not queue events".format(self.__class__.__name__.lower()))
            return
        try:
            formatted_event = self.format_event(raw_event)
            if formatted_event:
                self.queued_events.append(formatted_event)
        except Exception as e:
            logger.critical("formatter error: "+str(e))
        if len(self.queued_events) >= self.max_queue_length:
            formatted_squashed_event = self.squash_queued_events()
            logger.debug("merge {} queued events and flush".format(self.max_queue_length))
            self.forward_formatted(formatted_squashed_event)
            self.queued_events = []

    def squash_queued_events(self):
        instance = self.formatter()
        return instance.squash_queued_events(self.queued_events)
        return None

    def forward(self, raw_event):
        try:
            known_abbreviations = {
                "HOSTNAME": "host_name",
                "SERVICEDESC": "service_description",
                "NOTIFICATIONTYPE": "notification_type",
            }
            for abbr in known_abbreviations:
                if abbr in raw_event:
                    raw_event[known_abbreviations[abbr]] = raw_event[abbr]
            if "service_description" in raw_event:
                known_abbreviations = {
                    "SERVICESTATE": "state",
                    "SERVICEOUTPUT": "output",
                }
            else:
                known_abbreviations = {
                    "HOSTSTATE": "state",
                    "HOSTOUTPUT": "output",
                }
            for abbr in known_abbreviations:
                if abbr in raw_event:
                    raw_event[known_abbreviations[abbr]] = raw_event[abbr]
            if not "omd_site" in raw_event:
                raw_event["omd_site"] = os.environ.get("OMD_SITE", "get https://omd.consol.de/docs/omd")
            raw_event["originating_host"] = socket.gethostname()
            raw_event["originating_fqdn"] = socket.getfqdn()
            formatted_event = self.format_event(raw_event)
        except Exception as e:
            logger.critical("formatter error: "+str(e))
            formatted_event = None

        self.forward_formatted(formatted_event)

    def forward_formatted(self, formatted_event):
        try:
            if formatted_event == None:
                success = True
            else:
                success = self.submit(formatted_event)
        except Exception as e:
            success = False
            logger.critical(e)
        self.initdb()
        if success:
            if self.baseclass_logs_summary:
                logger.info("forwarded {}".format(formatted_event.summary))
            self.flush()
        else:
            if self.baseclass_logs_summary:
                logger.info("forward failed, spooled {}".format(formatted_event.summary))
            self.spool(formatted_event)

    def formatter(self):
        try:
            module_name = self.__class__.__name__.lower()
            class_name = self.__class__.__name__+"Formatter"
            formatter_module = import_module('.formatter', package='notificationforwarder.'+module_name)
            formatter_module.logger = logger
            formatter_class = getattr(formatter_module, class_name)
            instance = formatter_class()
            return instance
        except ImportError:
            logger.debug("there is no module "+module_name)
            return None
        except Exception as e:
            logger.critical("formatter error: "+str(e))
            return None

    def format_event(self, raw_event):
        instance = self.formatter()
        return instance.format_event(raw_event)

    def connect(self):
        return True

    def disconnect(self):
        return True

    def initdb(self):
        db_file = os.environ["OMD_ROOT"] + '/var/tmp/' + self.name + '-notifications.db'
        self.table_name = "events_"+self.name
        sql_create = """CREATE TABLE IF NOT EXISTS """+self.table_name+""" (
                id INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                summary TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            )"""
        try:
            conn = sqlite3.connect(db_file)
            curr = conn.cursor()
            curr.execute(sql_create)
            conn.close()
        except Exception as e:
            logger.info("error initializing database {}: {}".format(db_file, str(e)))

    def spool(self, event):
        sql_insert = "INSERT INTO "+self.table_name+"(payload, summary) VALUES (?, ?)"
        sql_count = "SELECT COUNT(*) FROM "+self.table_name
        try:
            conn = sqlite3.connect(os.environ["OMD_ROOT"] + '/var/tmp/' + self.name + '-notifications.db')
            curr = conn.cursor()
            num_spooled_events = 0
            if type(event.payload) != list:
                print("INSERT {} {}".format(type(event.payload), event.payload))
                text = json.dumps(event.payload)
                summary = event.summary
                print("INSERT {} {}".format(type(text), text))
                print("INSERT {} {}".format(type(summary), summary))
                curr.execute(sql_insert, (text, summary))
                conn.commit()
                logger.warning("spooled "+summary)
                num_spooled_events += 1
            else:
                for subevent in event.payload:
                    text = json.dumps(subevent)
                    summary = event.summary.pop(0)
                    curr.execute(sql_insert, (text, summary))
                    conn.commit()
                    log.warning("spooled "+summary)
                    num_spooled_events += 1
            curr.execute(sql_count)
            spooled_events = curr.fetchone()[0]
            logger.warning("spooled {} elements, queue length is {}".format(num_spooled_events , spooled_events))
            conn.close()
        except Exception as e:
            logger.info("database "+str(e))
            logger.info(event.__dict__)

    def flush(self):
        sql_delete = "DELETE FROM "+self.table_name+" WHERE CAST(STRFTIME('%s', timestamp) AS INTEGER) < ?"
        sql_count = "SELECT COUNT(*) FROM "+self.table_name
        sql_select = "SELECT id, payload, summary FROM "+self.table_name+" ORDER BY id LIMIT 10"
        sql_delete_id = "DELETE FROM "+self.table_name+" WHERE id = ?"
        with open(os.environ["OMD_ROOT"]+"/tmp/"+self.name+"-flush.lock", "w") as lock_file:
            try:
                fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug("locked")
                locked = True
            except IOError as e:
                logger.debug("lock failed: "+str(e))
                locked = False
            if locked:
                try:
                    conn = sqlite3.connect(os.environ["OMD_ROOT"] + '/var/tmp/' + self.name + '-notifications.db')
                    curr = conn.cursor()
                    outdated = int(time.time() - 60*MAXAGE)
                    curr.execute(sql_delete, (outdated,))
                    dropped = curr.rowcount
                    if dropped:
                        logger.info("dropped {} outdated events".format(dropped))
                    last_spooled_events = 0
                    while True:
                        curr.execute(sql_count)
                        spooled_events = curr.fetchone()[0]
                        if spooled_events:
                            logger.info("there are {} spooled events to be re-sent".format(spooled_events))
                        else:
                            break
                        if last_spooled_events == spooled_events:
                            if spooled_events != 0:
                                logger.critical("{} spooled events could not be submitted".format(last_spooled_events))
                            break
                        else:
                            curr.execute(sql_select)
                            id_events = curr.fetchall()
                            for id, payload, summary in id_events:
                                event = FormattedEvent()
                                event.is_heartbeat = False
                                event.payload = json.loads(payload)
                                event.summary = summary
                                if self.submit(event):
                                    curr.execute(sql_delete_id, (id, ))
                                    logger.info("delete spooled event {}".format(id))
                                    conn.commit()
                                else:
                                    logger.critical("event {} spooled again".format(id))
                            last_spooled_events = spooled_events
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.critical("database flush failed")
                    logger.critical(e)
            else:
                logger.debug("missed the flush lock")

    def no_more_logging(self):
        # this is called in the forwarder. If the forwarder already wrote
        # it's own logs and writing the summary by the baseclass is not
        # desired.
        self.baseclass_logs_summary = False



class NotificationFormatter(metaclass=ABCMeta):
    @abstractmethod
    def format_event(self):
        pass


class FormattedEvent(metaclass=ABCMeta):
    def __init__(self):
        self.payload = None
        self.summary = "empty event"

    def set_payload(self, payload):
        self.payload = payload

    def set_summary(self, summary):
        self.summary = summary
