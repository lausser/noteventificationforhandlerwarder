from abc import ABCMeta, abstractmethod
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

import logging
from coshsh.util import setup_logging


logger = None

def new(target_name, tag, decider, verbose, debug, runneropts):

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

    setup_logging(logdir=os.environ["OMD_ROOT"]+"/var/log", logfile=logger_name+".log", scrnloglevel=scrnloglevel, txtloglevel=txtloglevel, format="%(asctime)s %(process)d - %(levelname)s - %(message)s")
    logger = logging.getLogger(logger_name)
    try:
        if '.' in target_name:
            module_name, class_name = target_name.rsplit('.', 1)
        else:
            module_name = target_name
            class_name = target_name.capitalize()+"Runner"
        runner_module = import_module('eventhandler.'+module_name+'.runner', package='eventhandler.'+module_name)
        runner_class = getattr(runner_module, class_name)

        instance = runner_class(runneropts)
        instance.__module_file__ = runner_module.__file__
        instance.name = target_name
        if tag:
            instance.tag = tag
        instance.runner_name = runner_name
        instance.decider_name = decider

        # so we can use logger.info(...) in the single modules
        runner_module.logger = logging.getLogger(logger_name)
        base_module = import_module('.baseclass', package='eventhandler')
        base_module.logger = logging.getLogger(logger_name)

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
            def handler(signum, frame):
                raise RunnerTimeoutError(error_message)

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
            class_name = self.decider_name.capitalize()+"Decider"
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
        try:
            decided_event = DecidedEvent(raw_event)
            instance.decide_and_prepare(decided_event)
            return decided_event
        except Exception as e:
            logger.critical("when deciding based on this {} with this {} there was an error <{}>".format(str(raw_event), instance.__class__.__name__+"@"+instance.__module_file__, str(e)))
            return None

    def run(self, raw_event):
        try:
            decided_event = self.decide_and_prepare_event(raw_event)
            if decided_event and not decided_event.is_complete():
                logger.critical("a decided event {} must have the attributes payload and summary".format(decided_event.__class__.__name__))
                decided_event = None
        except Exception as e:
            try:
                decided_event
            except NameError:
                logger.critical("raw event {} caused error {}".format(str(raw_event), str(e)))
            decided_event = None
        if decided_event:
            success = self.run_decided(decided_event)

    def run_decided(self, decided_event):
        decide_exception_msg = None
        try:
            if decided_event == None:
                success = True
            else:
                success = self.run(decided_event)
        except Exception as e:
            success = False
            decide_exception_msg = str(e)

        if success:
            if self.baseclass_logs_summary:
                logger.info("ran {}".format(decided_event.summary))
            return True
        else:
            if decide_exception_msg:
                logger.critical("run failed with exception <{}>, event was <{}>".format(format_exception_msg, decided_event.summary))
            elif self.baseclass_logs_summary:
                logger.warning("run failed for {}".format(decided_event.summary))
            return False


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
        self._payload = None
        self._summary = None
        self._runneropts = {}

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

