from abc import ABCMeta, abstractmethod
from importlib import import_module
import os
import socket
import traceback
import signal
import functools
import threading
import errno
import fcntl
import time
import random
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


logger = None

def new(target_name, tag, formatter_name, verbose, debug, forwarder_opts, reporter_name=None, reporter_opts={}):

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

    if "logfile_backups" in forwarder_opts:
        backup_count = int(forwarder_opts["logfile_backups"])
        del forwarder_opts["logfile_backups"]
    elif "NOTIFICATIONFORWARDER_LOGFILE_BACKUPS" in os.environ:
        backup_count = int(os.environ["NOTIFICATIONFORWARDER_LOGFILE_BACKUPS"])
    else:
        backup_count = 3
    if "max_spool_minutes" in forwarder_opts:
        max_spool_minutes = int(forwarder_opts["max_spool_minutes"])
        del forwarder_opts["max_spool_minutes"]
    elif "NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES" in os.environ:
        max_spool_minutes = int(os.environ.get("NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES", 5))
    else:
        max_spool_minutes = 5


    setup_logging(logdir=os.environ["OMD_ROOT"]+"/var/log", logfile=logger_name+".log", scrnloglevel=scrnloglevel, txtloglevel=txtloglevel, format="%(asctime)s %(process)d - %(levelname)s - %(message)s", backup_count=backup_count)
    logger = logging.getLogger(logger_name)
    try:
        if '.' in target_name:
            module_name, class_name = target_name.rsplit('.', 1)
        else:
            module_name = target_name
            class_name = "".join([x.title() for x in target_name.split("_")])+"Forwarder"
        forwarder_module = import_module('notificationforwarder.'+module_name+'.forwarder', package='notificationforwarder.'+module_name)
        forwarder_class = getattr(forwarder_module, class_name)

        instance = forwarder_class(forwarder_opts)
        instance.__module_file__ = forwarder_module.__file__
        instance.name = target_name
        if tag:
            instance.tag = tag
        instance.forwarder_name = forwarder_name
        instance.formatter_name = formatter_name
        instance.reporter_name = reporter_name
        instance.reporter_opts = reporter_opts
        instance.max_spool_minutes = max_spool_minutes
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

class ReporterTimeoutError(Exception):
    pass

# this is my old implementation, which does not work
# in multi-threaded environments (e.g. a webserver based on
# bottle+waitress which listens for events and uses
# the notificationforwarder to deliver them to a ticketing tool.
#def timeout(seconds, error_message="Timeout"):
#    def decorator(func):
#        @functools.wraps(func)
#        def wrapper(*args, **kwargs):
#            def handler(signum, frame):
#                raise ForwarderTimeoutError(error_message)
#
#            original_handler = signal.signal(signal.SIGALRM, handler)
#            signal.alarm(seconds)
#            try:
#                result = func(*args, **kwargs)
#            finally:
#                signal.signal(signal.SIGALRM, original_handler)
#                signal.alarm(0)
#            return result
#        return wrapper
#    return decorator

# this is the new implementation, which starts a second thread
# which keeps an eye on the clock
def timeout(seconds, error_message="Timeout"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = [ForwarderTimeoutError(error_message)]
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    result[0] = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(seconds)
            if thread.is_alive():
                raise ForwarderTimeoutError(error_message)
            if isinstance(result[0], Exception):
                raise result[0]
            return result[0]
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
            self.dbconn = sqlite3.connect(self.db_file, check_same_thread=False)
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
            logger.critical("unknown error error in formatter instantiation: {}".format(e))
            return None

    def new_reporter(self, opts):
        try:
            module_name = self.reporter_name
            class_name = "".join([x.title() for x in self.reporter_name.split("_")])+"Reporter"
            reporter_module = import_module('.reporter', package='notificationforwarder.'+module_name)
            reporter_module.logger = logger
            reporter_class = getattr(reporter_module, class_name)
            instance = reporter_class(opts)
            instance.__module_file__ = reporter_module.__file__
            return instance
        except ImportError:
            logger.critical("found no reporter module {}".format(module_name))
            return None
        except Exception as e:
            logger.critical("unknown error error in reporter instantiation: {}".format(e))
            return None

    def format_event(self, raw_event):
        instance = self.new_formatter()
        if not "omd_site" in raw_event:
            raw_event["omd_site"] = os.environ.get("OMD_SITE", "get https://omd.consol.de/docs/omd")
        raw_event["omd_originating_host"] = socket.gethostname()
        raw_event["omd_originating_fqdn"] = socket.getfqdn()
        if not "omd_originating_timestamp" in raw_event:
            raw_event["omd_originating_timestamp"] = int(time.time())
        try:
            formatted_event = FormattedEvent(raw_event)
            instance.format_event(formatted_event)
            return formatted_event
        except Exception as e:
            logger.critical("when formatting this {} with this {} there was an error <{}>".format(str(raw_event), instance.__class__.__name__+"@"+instance.__module_file__, str(e)))
            return None

    def report_event(self, formatted_event):
        instance = self.new_reporter(self.reporter_opts)
        try:
            instance.report_event(formatted_event)
        except Exception as e:
            if instance:
                logger.critical("when reporting this {} with this {} there was an error <{}>".format(str(formatted_event.eventopts), instance.__class__.__name__+"@"+instance.__module_file__, str(e)))
            else:
                logger.critical("could not create a {} reporter instance with {}".format(self.reporter_name, self.reporter_opts))
            return None

    def forward(self, raw_event):
        try:
            enriched_event = self.enrich_raw_event(raw_event)
            formatted_event = self.format_event(enriched_event)
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
            result = self.forward_formatted(formatted_event)
            report_payload = {}
            if isinstance(result, bool):
                success = result
            elif isinstance(result, dict):
                success = result.get('success', False)
                report_payload = result.get('report_payload', {})
            else:
                # Unexpected type; treat as failure
                success = False
            if not success and not formatted_event.is_heartbeat:
                self.spool(raw_event)
            if self.reporter_name:
                formatted_event.eventopts["forwarder_name"] = self.forwarder_name
                formatted_event.eventopts["forwarder_tag"] = self.tag if hasattr(self, "tag") else ""
                formatted_event.eventopts["forwarder_success"] = success
                formatted_event.eventopts["formatter_name"] = self.formatter_name
                formatted_event.eventopts["formatter_summary"] = formatted_event.summary
                if report_payload:
                    formatted_event.eventopts["forwarder_report_payload"] = report_payload
                self.report_event(formatted_event)


    def forward_multiple(self, raw_event):
        # this method requires a formatter which implements a method split_events!
        instance = self.new_formatter()
        try:
            raw_event_list = instance.split_events(raw_event)
            instance = None
            logger.debug(f"received a payload with {len(raw_event_list)} single events")
            for raw_event in raw_event_list:
                self.forward(raw_event)
        except Exception as e:
            logger.critical(f"error split_events failed for {raw_event}")

    def enrich_raw_event(self, raw_event):
        if not "omd_site" in raw_event:
            raw_event["omd_site"] = os.environ.get("OMD_SITE", "get https://omd.consol.de/docs/omd")
        raw_event["omd_originating_host"] = socket.gethostname()
        raw_event["omd_originating_fqdn"] = socket.getfqdn()
        raw_event["omd_originating_timestamp"] = int(time.time())
        empty_macros = []
        for macro in raw_event:
            # remove all the macros which have not been given a value
            # by the nagios config
            if isinstance(raw_event[macro], dict) or isinstance(raw_event[macro], list):
                continue
            raw_event[macro] = str(raw_event[macro])
            if raw_event[macro] == "$":
                empty_macros.append(macro)
            elif re.search(r'^\$\w+\$', raw_event[macro]):
                empty_macros.append(macro)
        for macro in empty_macros:
            del raw_event[macro]
        return raw_event

    def forward_formatted(self, formatted_event):
        try:
            """probe() checks if a forwarder is principally capable to submit
            an event. It is mostly used to contact an api and confirm that
            it is alive. After failed attempts, when there are spooled events
            in the database, a call to probe() returning True can tell the
            forwarder that the events now can be flushed.
            """
            if self.num_spooled_events() and (not hasattr(self, "probe") or self.probe()):
                self.flush()
        except Exception as e:
            logger.critical("flush probe failed with exception <{}>".format(str(e)))

        format_exception_msg = None
        try:
            if formatted_event == None:
                success = True
            else:
                result = self.submit(formatted_event)
                if isinstance(result, bool):
                    success = result
                elif isinstance(result, dict):
                    success = result.get('success', False)
                    report_payload = result.get('report_payload', {})
                    if success and report_payload:
                        # If forwarding was sucessful and we got
                        # valuable information for the reporter, then
                        # return a dict.
                        success = result
                else:
                    # Unexpected type; treat as failure
                    success = False
        except Exception as e:
            success = False
            format_exception_msg = str(e)

        if success:
            if self.baseclass_logs_summary:
                logger.info("forwarded {}".format(formatted_event.summary))
            return success
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

    def acquire_lock_with_retry(self, lock_file, max_attempts=3, base_delay=0.1):
        for attempt in range(max_attempts):
            try:
                fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug("flush lock set")
                return True
            except IOError as e:
                logger.debug(f"flush lock failed (attempt {attempt + 1}): {str(e)}")
                if attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                    time.sleep(delay)
        return False

    def flush(self):
        sql_delete = "DELETE FROM "+self.table_name+" WHERE CAST(STRFTIME('%s', timestamp) AS INTEGER) < ?"
        sql_count = "SELECT COUNT(*) FROM "+self.table_name
        sql_select = "SELECT id, payload FROM "+self.table_name+" ORDER BY id LIMIT 10"
        sql_delete_id = "DELETE FROM "+self.table_name+" WHERE id = ?"
        with open(self.db_lock_file, "w") as lock_file:
            locked = self.acquire_lock_with_retry(lock_file)
            if locked:
                try:
                    outdated = int(time.time() - 60*self.max_spool_minutes)
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
                    logger.critical(f"database flush+resubmit failed: {e}")
                fcntl.lockf(lock_file, fcntl.LOCK_UN)
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
        self._forwarder_opts = {}
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
        return self._forwarder_opts

    @forwarderopts.setter
    def forwarderopts(self, forwarder_opts):
        self._forwarder_opts = forwarder_opts

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


class NotificationReporter(metaclass=ABCMeta):
    def __init__(self, reporter_opts):
        for opt in reporter_opts:
            setattr(self, opt, reporter_opts[opt])

    @abstractmethod
    def report_event(self, formatted_event):
        pass


