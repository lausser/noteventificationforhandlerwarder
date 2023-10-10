from abc import ABCMeta, abstractmethod
from importlib import import_module
import os
import socket
import traceback
import signal
import functools
import errno
import fcntl
import time
try:
    import simplejson as json
except ImportError:
    import json
from importlib import import_module
from importlib.util import find_spec, module_from_spec

import sqlite3
import logging
from coshsh.util import setup_logging


MAXAGE = 5


logger = None

def new(target_name, tag, verbose, debug, receiveropts):

    if verbose:
        scrnloglevel = logging.INFO
    else:
        scrnloglevel = 100
    if debug:
        scrnloglevel = logging.DEBUG
        txtloglevel = logging.DEBUG
    else:
        txtloglevel = logging.INFO
    if tag:
        logger_name = "notificationforwarder_"+target_name+"_"+tag
    else:
        logger_name = "notificationforwarder_"+target_name

    setup_logging(logdir=os.environ["OMD_ROOT"]+"/var/log", logfile=logger_name+".log", scrnloglevel=scrnloglevel, txtloglevel=txtloglevel, format="%(asctime)s %(process)d - %(levelname)s - %(message)s")
    logger = logging.getLogger(logger_name)
    try:
        if '.' in target_name:
            module_name, class_name = target_name.rsplit('.', 1)
        else:
            module_name = target_name
            class_name = target_name.capitalize()
        forwarder_module = import_module('notificationforwarder.'+module_name+'.forwarder', package='notificationforwarder.'+module_name)
        forwarder_class = getattr(forwarder_module, class_name)

        instance = forwarder_class(receiveropts)
        instance.__module_file__ = forwarder_module.__file__
        instance.name = target_name
        if tag:
            instance.tag = tag
        # so we can use logger.info(...) in the single modules
        forwarder_module.logger = logging.getLogger(logger_name)
        base_module = import_module('.baseclass', package='notificationforwarder')
        base_module.logger = logging.getLogger(logger_name)

    except Exception as e:
        raise ImportError('{} is not part of our forwarder collection!'.format(target_name))
    else:
        if not issubclass(forwarder_class, NotificationForwarder):
            raise ImportError("We currently don't have {}, but you are welcome to send in the request for it!".format(forwarder_class))

    return instance

class ForwarderTimeoutError(Exception):
    pass

def timeout(seconds, error_message="Timeout"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def handler(signum, frame):
                raise ForwarderTimeoutError(error_message)

            original_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.signal(signal.SIGALRM, original_handler)
                signal.alarm(0)
            return result
        return wrapper
    return decorator


class NotificationForwarder(object):
    """This is the base class where all Forwardes inherit from"""
    __metaclass__ = ABCMeta # replace with ...BaseClass(metaclass=ABCMeta):

    def __init__(self, opts):
        self.queued_events = []
        self.max_queue_length = 10
        self.sleep_after_flush = 0
        self.baseclass_logs_summary = True
        for opt in opts:
            setattr(self, opt, opts[opt])

    def probe(self):
        """Checks if a forwarder is principally able to submit an event.
        It is mostly used to contact an api and confirm that it is alive.
        After failed attempts, when there are spooled events in the database,
        a call to probe() can tell the forwarder that the events now can
        be flushed.
        """
        return True

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
        self.initdb()
        try:
            if not "omd_site" in raw_event:
                raw_event["omd_site"] = os.environ.get("OMD_SITE", "get https://omd.consol.de/docs/omd")
            raw_event["originating_host"] = socket.gethostname()
            raw_event["originating_fqdn"] = socket.getfqdn()
            formatted_event = self.format_event(raw_event)
            if not hasattr(formatted_event, "payload") and not hasattr(formatted_event, "summary"):
                logger.critical("a formatted event must have the attributes payload and summary")
                formatted_event = None
        except Exception as e:
            logger.critical("formatter error: "+str(e))
            formatted_event = None

        self.forward_formatted(formatted_event)

    def forward_formatted(self, formatted_event):
        try:
            if self.probe():
                self.flush()
        except Exception as e:
            logger.critical("flush probe failed with exception <{}>")

        format_exception_msg = None
        try:
            if formatted_event == None:
                success = True
            else:
                success = self.submit(formatted_event)
        except Exception as e:
            success = False
            format_exception_msg = str(e)

        if success:
            if self.baseclass_logs_summary:
                logger.info("forwarded {}".format(formatted_event.summary))
        else:
            if format_exception_msg:
                logger.critical("forward failed with exception <{}>, spooled <{}>".format(format_exception_msg, formatted_event.summary))
            elif self.baseclass_logs_summary:
                logger.warning("forward failed, spooled {}".format(formatted_event.summary))
            self.spool(formatted_event)

    def formatter(self):
        try:
            module_name = self.__class__.__name__.lower()
            class_name = self.__class__.__name__+"Formatter"
            formatter_module = import_module('.formatter', package='notificationforwarder.'+module_name)
            formatter_module.logger = logger
            formatter_class = getattr(formatter_module, class_name)
            instance = formatter_class()
            instance.__module_file__ = formatter_module.__file__
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
            self.dbconn = sqlite3.connect(db_file)
            self.dbcurs = self.dbconn.cursor()
            self.dbcurs.execute(sql_create)
            self.dbconn.commit()
        except Exception as e:
            logger.info("error initializing database {}: {}".format(db_file, str(e)))

    def num_spooled_events(self):
        sql_count = "SELECT COUNT(*) FROM "+self.table_name
        spooled_events = 999999999
        try:
            self.dbcurs.execute(sql_count)
            spooled_events = self.dbcurs.fetchone()[0]
        except Exception as e:
            logger.critical("database error "+str(e))
        return spooled_events


    def spool(self, event):
        sql_insert = "INSERT INTO "+self.table_name+"(payload, summary) VALUES (?, ?)"
        try:
            num_spooled_events = 0
            if type(event.payload) != list:
                text = json.dumps(event.payload)
                summary = event.summary
                self.dbcurs.execute(sql_insert, (text, summary))
                self.dbconn.commit()
                # has already been logged in forward_formatted
                # logger.warning("spooled "+summary)
                num_spooled_events += 1
            else:
                for subevent in event.payload:
                    text = json.dumps(subevent)
                    summary = event.summary.pop(0)
                    sefl.dbcurs.execute(sql_insert, (text, summary))
                    self.dbconn.commit()
                    log.warning("spooled "+summary)
                    num_spooled_events += 1
            spooled_events = self.num_spooled_events()
            logger.warning("spooling queue length is {}".format(spooled_events))
        except Exception as e:
            logger.critical("database error "+str(e))
            logger.info(event.__dict__)

    def flush(self):
        sql_delete = "DELETE FROM "+self.table_name+" WHERE CAST(STRFTIME('%s', timestamp) AS INTEGER) < ?"
        sql_count = "SELECT COUNT(*) FROM "+self.table_name
        sql_select = "SELECT id, payload, summary FROM "+self.table_name+" ORDER BY id LIMIT 10"
        sql_delete_id = "DELETE FROM "+self.table_name+" WHERE id = ?"
        with open(os.environ["OMD_ROOT"]+"/tmp/"+self.name+"-flush.lock", "w") as lock_file:
            try:
                fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug("flush lock set")
                locked = True
            except IOError as e:
                logger.debug("flush lock failed: "+str(e))
                locked = False
            if locked:
                try:
                    outdated = int(time.time() - 60*MAXAGE)
                    self.dbcurs.execute(sql_delete, (outdated,))
                    dropped = self.dbcurs.rowcount
                    if dropped:
                        logger.info("dropped {} outdated events".format(dropped))
                    last_spooled_events = 0
                    while True:
                        self.dbcurs.execute(sql_count)
                        spooled_events = self.dbcurs.fetchone()[0]
                        if spooled_events:
                            logger.info("there are {} spooled events to be re-sent".format(spooled_events))
                        else:
                            break
                        if last_spooled_events == spooled_events:
                            if spooled_events != 0:
                                logger.critical("{} spooled events could not be submitted".format(last_spooled_events))
                            break
                        else:
                            self.dbcurs.execute(sql_select)
                            id_events = self.dbcurs.fetchall()
                            for id, payload, summary in id_events:
                                event = FormattedEvent()
                                event.is_heartbeat = False
                                event.payload = json.loads(payload)
                                event.summary = summary
                                if self.submit(event):
                                    self.dbcurs.execute(sql_delete_id, (id, ))
                                    logger.info("delete spooled event {}".format(id))
                                    self.dbconn.commit()
                                else:
                                    logger.critical("event {} spooled again".format(id))
                            last_spooled_events = spooled_events
                    self.dbconn.commit()
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

    def __del__(self):
        try:
            if self.dbcursor:
                self.dbcursor.close()
            if self.dbconn:
                self.dbconn.commit()
                self.dbconn.close()
        except Exception as a:
            # don't care, we're finished anyway
            pass
    
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
