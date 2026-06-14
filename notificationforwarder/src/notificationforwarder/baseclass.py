from abc import ABCMeta, abstractmethod
import os
import socket
import functools
import threading
import time
import sys
try:
    import simplejson as json
except ImportError:
    import json

import logging
from notificationforwarder.util import setup_logging
from importlib import import_module

from notificationforwarder.component_loader import (
    ComponentLoadError,
    load_application_logger,
    load_formatter,
    load_forwarder,
    load_reporter,
)
from notificationforwarder.runtime_config import RuntimeConfig
from notificationforwarder.runtime_flow import (
    add_reporter_event_context,
    apply_forward_result,
    enrich_raw_event,
)
from notificationforwarder.spool import SpoolStore, acquire_lock_with_retry


logger = None

def new(target_name, tag, formatter_name, verbose, debug, forwarder_opts, reporter_name=None, reporter_opts={}, logger_type='text'):
    runtime_config = RuntimeConfig.from_inputs(
        target_name,
        tag,
        formatter_name,
        verbose,
        debug,
        forwarder_opts,
        reporter_name,
        reporter_opts,
        logger_type,
    )

    setup_logging(
        logdir=runtime_config.log_dir,
        logfile=runtime_config.logger_name + ".log",
        scrnloglevel=runtime_config.screen_log_level,
        txtloglevel=runtime_config.text_log_level,
        format="%(asctime)s %(process)d - %(levelname)s - %(message)s",
        backup_count=runtime_config.backup_count,
    )
    python_logger = logging.getLogger(runtime_config.logger_name)

    global logger
    logger = load_application_logger(runtime_config.logger_type, runtime_config.logger_name, python_logger)
    try:
        forwarder_module, forwarder_class, instance, _resolution = load_forwarder(
            runtime_config.target_name,
            runtime_config.forwarder_opts,
            logger,
        )
        instance.name = target_name
        if tag:
            instance.tag = tag
        instance.forwarder_name = runtime_config.forwarder_name
        instance.formatter_name = runtime_config.formatter_name
        instance.reporter_name = runtime_config.reporter_name
        instance.reporter_opts = runtime_config.reporter_opts
        instance.max_spool_minutes = runtime_config.max_spool_minutes
        instance.init_paths()
        instance.init_db()

        # Make app_logger available to modules
        base_module = import_module('.baseclass', package='notificationforwarder')
        base_module.logger = logger

    except ComponentLoadError as e:
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
        runtime_paths = RuntimeConfig.from_inputs(
            self.name,
            getattr(self, "tag", None),
            self.formatter_name,
            False,
            False,
            {},
        ).build_paths()
        self.db_file = runtime_paths.db_file
        self.db_lock_file = runtime_paths.db_lock_file

    def init_db(self):
        self.table_name = "events_"+self.forwarder_name
        try:
            self.spool_store = SpoolStore(self.db_file, self.table_name)
            self.spool_store.open()
            self.spool_store.init_db()
            self.dbconn = self.spool_store.connection
            self.dbcurs = self.spool_store.cursor
        except Exception as e:
            logger.info("error initializing database", {'db_file': self.db_file, 'exception': e})

    def new_formatter(self):
        try:
            instance, _resolution = load_formatter(self.formatter_name, logger)
            return instance
        except ComponentLoadError as e:
            logger.critical("found no formatter module", e.details)
            return None
        except Exception as e:
            logger.critical("unknown error in formatter instantiation", {'exception': e})
            return None

    def new_reporter(self, opts):
        try:
            instance, _resolution = load_reporter(self.reporter_name, opts, logger)
            return instance
        except ComponentLoadError as e:
            reporter_context = dict(e.details)
            reporter_context['reporter_opts'] = opts
            logger.critical("found no reporter module", reporter_context)
            return None
        except Exception as e:
            logger.critical("unknown error in reporter instantiation", {'exception': e})
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
            logger.critical("when formatting event there was an error", {
                'event_data': str(raw_event),
                'formatter_instance': instance,
                'exception': e,
                'exc_info': sys.exc_info()
            })
            return None

    def report_event(self, formatted_event):
        instance = self.new_reporter(self.reporter_opts)
        try:
            instance.report_event(formatted_event)
        except Exception as e:
            if instance:
                logger.critical("when reporting event there was an error", {
                    'event_data': str(formatted_event.eventopts),
                    'reporter_instance': instance,
                    'exception': e,
                    'exc_info': sys.exc_info()
                })
            else:
                logger.critical("could not create reporter instance", {
                    'reporter_name': self.reporter_name,
                    'reporter_opts': self.reporter_opts
                })
            return None

    def forward(self, raw_event):
        try:
            enriched_event = self.enrich_raw_event(raw_event)
            formatted_event = self.format_event(enriched_event)
            if formatted_event.is_discarded:
                if not formatted_event.is_discarded_silently:
                    if not formatted_event.summary:
                        formatted_event.summary = str(raw_event)
                    logger.info("discarded", {'formatted_event': formatted_event})
                formatted_event = None
            elif formatted_event and not formatted_event.is_complete():
                logger.critical("formatted event incomplete", {
                    'event_class': formatted_event.__class__.__name__
                })
                formatted_event = None
        except Exception as e:
            try:
                formatted_event
            except NameError:
                logger.critical("raw event caused error", {
                    'raw_event': str(raw_event),
                    'exception': e,
                    'exc_info': sys.exc_info()
                })
            formatted_event = None

        if formatted_event:
            result = self.forward_formatted(formatted_event)
            success, report_payload, error_message = apply_forward_result(result)
            if not success and not formatted_event.is_heartbeat:
                spooled = self.spool(raw_event)
                if spooled:
                    failure_context = {
                        'formatted_event': formatted_event,
                        'spooled': True,
                        'status': 'failed',
                    }
                    if error_message:
                        failure_context['exception'] = error_message
                    logger.warning("forward failed", failure_context)
                else:
                    unrecoverable_context = {
                        'formatted_event': formatted_event,
                        'raw_event': str(raw_event),
                        'status': 'failed',
                    }
                    if error_message:
                        unrecoverable_context['exception'] = error_message
                    logger.critical("delivery failed and event could not be persisted", unrecoverable_context)
            elif not success:
                failure_context = {
                    'formatted_event': formatted_event,
                    'status': 'failed',
                }
                if error_message:
                    failure_context['exception'] = error_message
                logger.warning("forward failed", failure_context)
            if self.reporter_name:
                add_reporter_event_context(
                    formatted_event,
                    self.forwarder_name,
                    self.formatter_name,
                    success,
                    report_payload,
                    self.tag if hasattr(self, "tag") else "",
                )
                self.report_event(formatted_event)


    def forward_multiple(self, raw_event):
        # this method requires a formatter which implements a method split_events!
        instance = self.new_formatter()
        try:
            raw_event_list = instance.split_events(raw_event)
            instance = None
            logger.debug("received payload with multiple events", {
                'split_count': len(raw_event_list)
            })
            for raw_event in raw_event_list:
                self.forward(raw_event)
        except Exception as e:
            logger.critical("split_events failed", {
                'raw_event': raw_event,
                'split_error': True,
                'exception': e
            })

    def enrich_raw_event(self, raw_event):
        return enrich_raw_event(raw_event)

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
            logger.critical("flush probe failed", {
                'exception': e,
                'exc_info': sys.exc_info()
            })

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
            return {
                'success': False,
                'error_message': str(e),
            }

        if success:
            if self.baseclass_logs_summary:
                logger.info("forwarded", {
                    'formatted_event': formatted_event,
                    'status': 'success'
                })
            return success
        return False


    def num_spooled_events(self):
        spooled_events = 999999999
        try:
            spooled_events = self.spool_store.count()
        except Exception as e:
            logger.critical("database error", {
                'database_error': True,
                'exception': e
            })
        return spooled_events


    def spool(self, raw_event):
        try:
            self.spool_store.enqueue(raw_event)
            spooled_events = self.num_spooled_events()
            logger.warning("spooling queue length", {
                'queue_length': spooled_events
            })
            return True
        except Exception as e:
            logger.critical("database error", {
                'database_error': True,
                'exception': e
            })
            logger.info("raw event details", {'raw_event': raw_event})
            return False

    def acquire_lock_with_retry(self, lock_file, max_attempts=3, base_delay=0.1):
        return acquire_lock_with_retry(lock_file, logger, max_attempts=max_attempts, base_delay=base_delay)

    def flush(self):
        with open(self.db_lock_file, "w") as lock_file:
            locked = self.acquire_lock_with_retry(lock_file)
            if locked:
                self.baseclass_logs_summary = True
                try:
                    dropped = self.spool_store.prune_expired(self.max_spool_minutes)
                    replay_attempted = 0
                    replayed = 0
                    stayed_in_spool = 0
                    deleted_trash = 0
                    if dropped:
                        logger.info("dropped outdated events", {
                            'spooled_count': dropped,
                            'action': 'dropped'
                        })
                    last_events_to_flush = 0
                    while True:
                        events_to_flush = self.num_spooled_events()
                        if events_to_flush:
                            logger.info("spooled events to be re-sent", {
                                'spooled_count': events_to_flush,
                                'action': 'resend'
                            })
                        else:
                            logger.debug("nothing left to flush", {})
                            break
                        if last_events_to_flush == events_to_flush:
                            if events_to_flush != 0:
                                logger.critical("spooled events could not be submitted", {
                                    'spooled_count': last_events_to_flush,
                                    'action': 'could_not_submit'
                                })
                            break
                        else:
                            id_events = self.spool_store.fetch_batch()
                            for id, text in id_events:
                                raw_event = self.spool_store.decode(text)
                                formatted_event = self.format_event(raw_event)
                                if formatted_event and formatted_event.is_discarded:
                                    deleted_trash += 1
                                    logger.info("discard spooled event during replay", {
                                        'event_id': id,
                                        'action': 'discard_during_replay'
                                    })
                                    self.spool_store.delete(id)
                                elif formatted_event:
                                    replay_attempted += 1
                                    try:
                                        result = self.submit(formatted_event)
                                        success, _report_payload, error_message = apply_forward_result(result)
                                    except Exception as e:
                                        success = False
                                        error_message = str(e)
                                    if success:
                                        self.spool_store.delete(id)
                                        replayed += 1
                                        logger.info("delete spooled event", {
                                            'spooled_count': 1,
                                            'event_id': id,
                                            'action': 'delete'
                                        })
                                    else:
                                        stayed_in_spool += 1
                                        context = {
                                            'event_id': id,
                                            'action': 'stays_in_spool'
                                        }
                                        if error_message:
                                            context['exception'] = error_message
                                        logger.critical("event stays in spool", context)
                                else:
                                    deleted_trash += 1
                                    logger.critical("could not format spooled event", {
                                        'raw_event': raw_event,
                                        'event_id': id,
                                        'spooled_count': 1,
                                        'action': 'could_not_format'
                                    })
                                    self.spool_store.delete(id)
                                    logger.info("delete trash event", {
                                        'event_id': id,
                                        'action': 'delete_trash'
                                    })
                            last_events_to_flush = events_to_flush
                    logger.info("spool replay summary", {
                        'attempted': replay_attempted,
                        'recovered_count': replayed,
                        'stays_in_spool_count': stayed_in_spool,
                        'deleted_trash_count': deleted_trash,
                        'dropped_count': dropped,
                    })
                    self.spool_store.commit()
                except Exception as e:
                    logger.critical("database flush+resubmit failed", {
                        'database_error': True,
                        'exception': e
                    })
                import fcntl

                fcntl.lockf(lock_file, fcntl.LOCK_UN)
            else:
                logger.info("concurrent flush suppressed", {})
                logger.debug("missed the flush lock", {})

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
            if hasattr(self, "spool_store") and self.spool_store:
                self.spool_store.close()
            elif hasattr(self, "dbconn") and self.dbconn:
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


class NotificationLogger(metaclass=ABCMeta):
    """
    Abstract base class for loggers

    Loggers receive structured context and format log entries appropriately.
    This allows switching between text and JSON formats without changing
    logging call sites.
    """

    def __init__(self, logger_name, python_logger):
        """
        Initialize logger

        Args:
            logger_name: Name of the logger (e.g., "notificationforwarder_webhook")
            python_logger: Underlying Python logging.Logger instance
        """
        self.logger_name = logger_name
        self.python_logger = python_logger
        self.omd_site = os.environ.get("OMD_SITE", "")
        self.originating_host = socket.gethostname()
        self.originating_fqdn = socket.getfqdn()

    @abstractmethod
    def log(self, level, message, context=None):
        """
        Log a message with structured context

        Args:
            level: Log level ('debug', 'info', 'warning', 'error', 'critical')
            message: Human-readable message
            context: Dict with structured context:
                - event: Raw event dict (eventopts)
                - formatted_event: FormattedEvent instance
                - exception: Exception object
                - exc_info: sys.exc_info() tuple for traceback
                - spooled: Boolean if event was spooled
                - forwarder_name: Name of forwarder
                - formatter_name: Name of formatter
                - reporter_name: Name of reporter
                - formatter_instance: Formatter instance
                - reporter_instance: Reporter instance
                - spooled_count: Number of spooled events
                - queue_length: Queue length
                - dropped_count: Number of dropped events
                - event_data: Raw event data
                - status: Status string
        """
        pass

    def debug(self, message, context=None):
        """Convenience method for debug level"""
        self.log('debug', message, context)

    def info(self, message, context=None):
        """Convenience method for info level"""
        self.log('info', message, context)

    def warning(self, message, context=None):
        """Convenience method for warning level"""
        self.log('warning', message, context)

    def error(self, message, context=None):
        """Convenience method for error level"""
        self.log('error', message, context)

    def critical(self, message, context=None):
        """Convenience method for critical level"""
        self.log('critical', message, context)
