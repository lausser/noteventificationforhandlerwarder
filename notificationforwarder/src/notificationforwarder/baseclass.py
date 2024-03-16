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
import re
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

def new(target_name, tag, formatter, verbose, debug, receiveropts):

    forwarder_name = target_name + ("_"+tag if tag else "")
    if verbose:
        scrnloglevel = logging.INFO
    else:
        scrnloglevel = 100
    if debug:
        scrnloglevel = logging.DEBUG
        txtloglevel = logging.DEBUG
    else:
        txtloglevel = logging.INFO
    logger_name = "notificationforwarder_"+forwarder_name

    setup_logging(logdir=os.environ["OMD_ROOT"]+"/var/log", logfile=logger_name+".log", scrnloglevel=scrnloglevel, txtloglevel=txtloglevel, format="%(asctime)s %(process)d - %(levelname)s - %(message)s")
    logger = logging.getLogger(logger_name)
    try:
        if '.' in target_name:
            module_name, class_name = target_name.rsplit('.', 1)
        else:
            module_name = target_name
            class_name = "".join([x.title() for x in target_name.split("_")])+"Forwarder"
        forwarder_module = import_module('notificationforwarder.'+module_name+'.forwarder', package='notificationforwarder.'+module_name)
        forwarder_class = getattr(forwarder_module, class_name)

        instance = forwarder_class(receiveropts)
        instance.__module_file__ = forwarder_module.__file__
        instance.name = target_name
        if tag:
            instance.tag = tag
        instance.forwarder_name = forwarder_name
        instance.formatter_name = formatter
        instance.init_paths()
        instance.init_db()

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

    def init_paths(self):
        self.db_file = os.environ["OMD_ROOT"] + '/var/tmp/notificationforwarder_' + self.forwarder_name + '_notifications.db'
        self.db_lock_file = os.environ["OMD_ROOT"]+"/tmp/notificationforwarder"+self.forwarder_name+"_flush.lock"

    def init_db(self):
        self.table_name = "events_"+self.forwarder_name
        sql_create = """CREATE TABLE IF NOT EXISTS """+self.table_name+""" (
                id INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            )"""
        try:
            self.dbconn = sqlite3.connect(self.db_file)
            self.dbcurs = self.dbconn.cursor()
            self.dbcurs.execute(sql_create)
            self.dbconn.commit()
        except Exception as e:
            logger.info("error initializing database {}: {}".format(self.db_file, str(e)))

    def new_formatter(self):
        try:
            module_name = self.formatter_name
            class_name = "".join([x.title() for x in self.formatter_name.split("_")])+"Formatter"
            formatter_module = import_module('.formatter', package='notificationforwarder.'+module_name)
            formatter_module.logger = logger
            formatter_class = getattr(formatter_module, class_name)
            instance = formatter_class()
            instance.__module_file__ = formatter_module.__file__
            return instance
        except ImportError:
            logger.critical("found no formatter module {}".format(module_name))
            return None
        except Exception as e:
            logger.critical("unknown error error in formatter instntiation: {}".format(e))
            return None

    def probe(self):
        """Checks if a forwarder is principally able to submit an event.
        It is mostly used to contact an api and confirm that it is alive.
        After failed attempts, when there are spooled events in the database,
        a call to probe() can tell the forwarder that the events now can
        be flushed.
        """
        return True

    def format_event(self, raw_event):
        instance = self.new_formatter()
        if not "omd_site" in raw_event:
            raw_event["omd_site"] = os.environ.get("OMD_SITE", "get https://omd.consol.de/docs/omd")
        raw_event["omd_originating_host"] = socket.gethostname()
        raw_event["omd_originating_fqdn"] = socket.getfqdn()
        raw_event["omd_originating_timestamp"] = int(time.time())
        try:
            empty_macros = []
            for macro in raw_event:
                # remove all the macros which have not been given a value
                # by the nagios config
                raw_event[macro] = str(raw_event[macro])
                if raw_event[macro] == "$":
                    empty_macros.append(macro)
                elif re.search(r'^\$\w+\$', raw_event[macro]):
                    empty_macros.append(macro)
            for macro in empty_macros:
                del raw_event[macro]
            formatted_event = FormattedEvent(raw_event)
            instance.format_event(formatted_event)
            return formatted_event
        except Exception as e:
            logger.critical("when formatting this {} with this {} there was an error <{}>".format(str(raw_event), instance.__class__.__name__+"@"+instance.__module_file__, str(e)))
            return None

    def forward(self, raw_event):
        try:
            formatted_event = self.format_event(raw_event)
            if formatted_event.is_discarded:
                if not formatted_event.is_discarded_silently:
                    if not formatted_event.summary:
                        formatted_event.summary = str(raw_event)
                    logger.info("discarded {}".format(formatted_event.summary))
                formatted_event = None
            elif formatted_event and not formatted_event.is_complete():
                logger.critical("a formatted event {} must have the attributes payload and summary".format(formatted_event.__class__.__name__))
                formatted_event = None
        except Exception as e:
            try:
                formatted_event
            except NameError:
                logger.critical("raw event {} caused error {}".format(str(raw_event), str(e)))
            formatted_event = None
        if formatted_event:
            success = self.forward_formatted(formatted_event)
            if not success and not formatted_event.is_heartbeat:
                self.spool(raw_event)

    def forward_formatted(self, formatted_event):
        try:
            if self.num_spooled_events() and self.probe():
                self.flush()
        except Exception as e:
            logger.critical("flush probe failed with exception <{}>".format(str(e)))

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
            return True
        else:
            if format_exception_msg:
                logger.critical("forward failed with exception <{}>, spooled <{}>".format(format_exception_msg, formatted_event.summary))
            elif self.baseclass_logs_summary:
                logger.warning("forward failed, spooling {}".format(formatted_event.summary))
            return False


    def num_spooled_events(self):
        sql_count = "SELECT COUNT(*) FROM "+self.table_name
        spooled_events = 999999999
        try:
            self.dbcurs.execute(sql_count)
            spooled_events = self.dbcurs.fetchone()[0]
        except Exception as e:
            logger.critical("database error "+str(e))
        return spooled_events


    def spool(self, raw_event):
        sql_insert = "INSERT INTO "+self.table_name+"(payload) VALUES (?)"
        try:
            text = json.dumps(raw_event)
            self.dbcurs.execute(sql_insert, (text,))
            self.dbconn.commit()
            spooled_events = self.num_spooled_events()
            logger.warning("spooling queue length is {}".format(spooled_events))
        except Exception as e:
            logger.critical("database error "+str(e))
            logger.info(raw_event)

    def flush(self):
        sql_delete = "DELETE FROM "+self.table_name+" WHERE CAST(STRFTIME('%s', timestamp) AS INTEGER) < ?"
        sql_count = "SELECT COUNT(*) FROM "+self.table_name
        sql_select = "SELECT id, payload FROM "+self.table_name+" ORDER BY id LIMIT 10"
        sql_delete_id = "DELETE FROM "+self.table_name+" WHERE id = ?"
        with open(self.db_lock_file, "w") as lock_file:
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
                    last_events_to_flush = 0
                    while True:
                        events_to_flush = self.num_spooled_events()
                        if events_to_flush:
                            logger.info("there are {} spooled events to be re-sent".format(events_to_flush))
                        else:
                            logger.debug("nothing left to flush")
                            break
                        if last_events_to_flush == events_to_flush:
                            if events_to_flush != 0:
                                logger.critical("{} spooled events could not be submitted".format(last_events_to_flush))
                            break
                        else:
                            self.dbcurs.execute(sql_select)
                            id_events = self.dbcurs.fetchall()
                            for id, text in id_events:
                                raw_event = json.loads(text)
                                formatted_event = self.format_event(raw_event)
                                if formatted_event:
                                    #
                                    success = self.submit(formatted_event)
                                    if success:
                                        self.dbcurs.execute(sql_delete_id, (id, ))
                                        logger.info("delete spooled event {}".format(id))
                                        self.dbconn.commit()
                                    else:
                                        logger.critical("event {} stays in spool".format(id))
                                else:
                                    logger.critical("could not format spooled {}. sorry, but i will delete this garbage with id {}".format(raw_event, id))
                                    self.dbcurs.execute(sql_delete_id, (id, ))
                                    logger.info("delete trash event {}".format(id))
                                    self.dbconn.commit()
                            last_events_to_flush = events_to_flush
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

    def connect(self):
        return True

    def disconnect(self):
        return True

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
    def __init__(self, eventopts):
        self._is_heartbeat = False
        self._eventopts = eventopts
        self._payload = None
        self._summary = None
        self._forwarderopts = {}
        self._discarded = False
        self._discarded_silently = True

    @property
    def eventopts(self):
        return self._eventopts

    @property
    def is_heartbeat(self):
        return self._is_heartbeat

    @is_heartbeat.setter
    def is_heartbeat(self, value):
        self._is_heartbeat = value

    @property
    def payload(self):
        return self._payload

    @payload.setter
    def payload(self, payload):
        self._payload = payload

    @property
    def summary(self):
        return self._summary

    @summary.setter
    def summary(self, summary):
        self._summary = summary

    @property
    def forwarderopts(self):
        return self._forwarderopts

    @forwarderopts.setter
    def forwarderopts(self, forwarderopts):
        self._forwarderopts = forwarderopts

    @property
    def is_discarded_silently(self):
        return self._discarded_silently

    @property
    def is_discarded(self):
        return self._discarded

    def is_complete(self):
        if self._payload == None or self._summary == None:
            return False
        return True

    def discard(self, silently=True):
        self._discarded = True
        self._discarded_silently = True if silently else False
