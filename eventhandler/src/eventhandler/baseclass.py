from abc import ABCMeta, abstractmethod
import os
import re
import socket
import traceback
import signal
import functools
import errno
import fcntl
import time
import subprocess
try:
    import simplejson as json
except ImportError:
    import json
from importlib import import_module
from importlib.util import find_spec, module_from_spec

import logging
from coshsh.util import setup_logging


logger = None

def new(target_name, tag, decider, verbose, debug, runneropts, logger_type='text'):

    runner_name = target_name + ("_"+tag if tag else "")
    if verbose:
        scrnloglevel = logging.INFO
    else:
        scrnloglevel = 100
    if debug:
        scrnloglevel = logging.DEBUG
        txtloglevel = logging.DEBUG
    else:
        txtloglevel = logging.INFO
    logger_name = "eventhandler_"+runner_name

    if "logfile_backups" in runneropts:
        backup_count = int(runneropts["logfile_backups"])
        del runneropts["logfile_backups"]
    elif "EVENTHANDLER_LOGFILE_BACKUPS" in os.environ:
        backup_count = int(os.environ["EVENTHANDLER_LOGFILE_BACKUPS"])
    else:
        backup_count = 3

    # Setup Python logging infrastructure (same for all logger types)
    setup_logging(logdir=os.environ["OMD_ROOT"]+"/var/log", logfile=logger_name+".log", scrnloglevel=scrnloglevel, txtloglevel=txtloglevel, format="%(asctime)s %(process)d - %(levelname)s - %(message)s", backup_count=backup_count)
    python_logger = logging.getLogger(logger_name)

    # Instantiate application logger (text or json)
    try:
        if '.' in logger_type:
            module_name, class_name = logger_type.rsplit('.', 1)
        else:
            module_name = logger_type
            class_name = "".join([x.title() for x in logger_type.split("_")])+"Logger"
        logger_module = import_module('eventhandler.'+module_name+'.logger',
                                      package='eventhandler.'+module_name)
        logger_class = getattr(logger_module, class_name)
        logger = logger_class(logger_name, python_logger)
    except Exception as e:
        # Fallback to text logger
        from eventhandler.text.logger import TextLogger
        logger = TextLogger(logger_name, python_logger)
        logger.warning("Could not load logger type, falling back to text", {'exception': e})
    try:
        if '.' in target_name:
            module_name, class_name = target_name.rsplit('.', 1)
        else:
            module_name = target_name
            class_name = "".join([x.title() for x in target_name.split("_")])+"Runner"
        runner_module = import_module('eventhandler.'+module_name+'.runner', package='eventhandler.'+module_name)
        runner_class = getattr(runner_module, class_name)

        instance = runner_class(runneropts)
        instance.__module_file__ = runner_module.__file__
        instance.name = target_name
        if tag:
            instance.tag = tag
        instance.runner_name = runner_name
        instance.decider_name = decider

        # Make app_logger available to modules
        runner_module.logger = logger
        base_module = import_module('.baseclass', package='eventhandler')
        base_module.logger = logger

    except Exception as e:
        raise ImportError('{} is not part of our runner collection!'.format(target_name))
    else:
        if not issubclass(runner_class, EventhandlerRunner):
            raise ImportError("We currently don't have {}, but you are welcome to send in the request for it!".format(runner_class))

    return instance

class RunnerTimeoutError(Exception):
    pass

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


class EventhandlerPythonRunner(object):
    pass

class EventhandlerRunner(object):
    """This is the base class where all Runners inherit from"""
    __metaclass__ = ABCMeta # replace with ...BaseClass(metaclass=ABCMeta):

    def __init__(self, opts):
        self.baseclass_logs_summary = True
        for opt in opts:
            setattr(self, opt, opts[opt])

    def new_decider(self):
        try:
            module_name = self.decider_name
            class_name = "".join([x.title() for x in self.decider_name.split("_")])+"Decider"
            decider_module = import_module('.decider', package='eventhandler.'+module_name)
            decider_module.logger = logger
            decider_class = getattr(decider_module, class_name)
            instance = decider_class()
            instance.__module_file__ = decider_module.__file__
            return instance
        except ImportError:
            logger.critical("found no decider module {}".format(module_name))
            return None
        except Exception as e:
            logger.critical("unknown error error in decider instantiation: {}".format(e))
            return None


    def decide_and_prepare_event(self, raw_event):
        instance = self.new_decider()
        if not "omd_site" in raw_event:
            raw_event["omd_site"] = os.environ.get("OMD_SITE", "get https://omd.consol.de/docs/omd")
        raw_event["omd_originating_host"] = socket.gethostname()
        raw_event["omd_originating_fqdn"] = socket.getfqdn()
        raw_event["omd_originating_timestamp"] = int(time.time())
        raw_event["omd_originating_timestamp"] = int(time.time())
        try:
            decided_event = DecidedEvent(raw_event)
            setattr(instance, "runner", self.runner_name[:-len("_"+self.tag)] if hasattr(self, "tag") and self.runner_name.endswith("_"+self.tag) else self.runner_name)
            instance.decide_and_prepare(decided_event)
            return decided_event
        except Exception as e:
            logger.critical("when deciding based on this {} with this {} there was an error <{}>".format(str(raw_event), instance.__class__.__name__+"@"+instance.__module_file__, str(e)))
            return None

    def handle(self, raw_event):
        success = False
        if "SERVICEDESC" in raw_event:
            if re.match(r'(Return\ code\ of|Timed\ Out|timed\ out|check_by_ssh:\ Remote\ command|service\ check\ orphaned)', raw_event["SERVICEDESC"]):
                return True
        try:
            decided_event = self.decide_and_prepare_event(raw_event)
            if decided_event.is_discarded:
                if not decided_event.is_discarded_silently:
                    if not decided_event.summary:
                        decided_event.summary = str(raw_event)
                    logger.info("discarded: {}".format(decided_event.summary))
                decided_event = None
            elif decided_event and not decided_event.is_complete():
                logger.critical("a decided event {} must have the attributes payload and summary. {}".format(decided_event.__class__.__name__, decided_event.__dict__))
                decided_event = None
        except Exception as e:
            try:
                decided_event
            except NameError:
                logger.critical("raw event {} caused error {}".format(str(raw_event), str(e)))
            decided_event = None
            success = None
        if decided_event:
            self.overwrite_attributes(decided_event.payload)
            success, stdout, stderr = self.run_decided(decided_event)
            if hasattr(self, "forwarder"):
                raw_event["NOTIFICATIONTYPE"] = "EVENTHANDLER"
                raw_event["NOTIFICATIONAUTHOR"] = self.runner_name
                raw_event["NOTIFICATIONCOMMENT"] = "stdout: {}, stderr: {}".format(stdout if stdout else "-", stderr if stderr else "-")
                if "SERVICEDESC" in raw_event:
                    if success:
                        raw_event["SERVICESTATE"] = "OK"
                    else:
                        raw_event["SERVICESTATE"] = "CRITICAL"
                else:
                    if success:
                        raw_event["HOSTSTATE"] = "UP"
                    else:
                        raw_event["HOSTSTATE"] = "DOWN"
                raw_event["eventhandler_success"] = success
                if success != None:
                    # none means, python runner has aborted intentionally
                    self.forwarder.forward(raw_event)
        return success

    def overwrite_attributes(self, payload):
        # paload can overwrite runneropts
        for k in payload:
            if hasattr(self, k):
                setattr(self, k, payload[k])

    def run_decided(self, decided_event):
        decide_exception_msg = None
        stdout, stderr, exit_code = None, None, 0
        try:
            if decided_event == None:
                success = True
            else:
                runner_res = self.run(decided_event)
                if isinstance(runner_res, str):
                    # The runner returns a command line
                    command = runner_res
                    logger.debug(f"command is {command}")
                    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = proc.communicate()
                    exit_code = proc.wait()
                    success = True if exit_code == 0 else False
                elif runner_res in [True, False]:
                    # The runner is pure python or executed a command itself or
                    # did something else. It only reports success or failure to the baseclass.
                    # No stdout, stderr. the runner has to write output itself
                    success = runner_res
                elif runner_res == None:
                    # runner discard
                    success = False
                    self.no_more_logging()
                else:
                    success = False
        except Exception as e:
            success = False
            decide_exception_msg = str(e)

        if success:
            if self.baseclass_logs_summary:
                logger.info("{}".format(decided_event.summary))
                logger.debug("stdout {}, stderr {}".format(stdout if stdout else "", stderr if stderr else ""))
            return True, stdout, stderr
        else:
            if stderr:
                logger.critical("run failed: stdout {}, stderr {}, event {}".format(stdout if stdout else "", stderr if stderr else "", decided_event.summary))
            elif decide_exception_msg:
                logger.critical("run failed: exception <{}>, event was <{}>".format(decide_exception_msg, decided_event.summary))
            elif self.baseclass_logs_summary:
                logger.critical("run failed: stdout {}, stderr {}, exitcode {}, event {}".format(stdout if stdout else "", stderr if stderr else "", exit_code, decided_event.summary))
            return False, stdout, stderr


    def no_more_logging(self):
        # this is called in the runner. If the runner already wrote
        # it's own logs and writing the summary by the baseclass is not
        # desired.
        self.baseclass_logs_summary = False

    def connect(self):
        return True

    def disconnect(self):
        return True

    def __del__(self):
        try:
            pass
        except Exception as a:
            # don't care, we're finished anyway
            pass
    
class EventhandlerDecider(metaclass=ABCMeta):
    @abstractmethod
    def decide_and_prepare(self):
        pass


class DecidedEvent(metaclass=ABCMeta):
    def __init__(self, eventopts):
        self._eventopts = eventopts
        for k in self._eventopts:
            if isinstance(self._eventopts[k], str) and self._eventopts[k].isdigit():
                self._eventopts[k] = int(self._eventopts[k])
        self._payload = None
        self._summary = str(self._eventopts)
        self._runneropts = {}
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
    def runneropts(self):
        return self._runneropts

    @runneropts.setter
    def runneropts(self, runneropts):
        self._runneropts = runneropts

    def is_complete(self):
        if self._payload == None or self._summary == None:
            return False
        return True

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


class EventhandlerLogger(metaclass=ABCMeta):
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
            logger_name: Name of the logger (e.g., "eventhandler_bash")
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
                - decided_event: DecidedEvent instance
                - exception: Exception object
                - exc_info: sys.exc_info() tuple for traceback
                - runner_name: Name of runner
                - decider_name: Name of decider
                - decider_instance: Decider instance
                - stdout: Command stdout
                - stderr: Command stderr
                - exit_code: Command exit code
                - command: Shell command executed
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

