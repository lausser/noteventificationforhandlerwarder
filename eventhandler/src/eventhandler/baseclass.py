from abc import ABCMeta, abstractmethod
import os
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
        if decided_event:
            self.overwrite_attributes(decided_event.payload)
            success = self.run_decided(decided_event)

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
            return True
        else:
            if stderr:
                logger.critical("run failed: stdout {}, stderr {}, event {}".format(stdout if stdout else "", stderr if stderr else "", decided_event.summary))
            elif decide_exception_msg:
                logger.critical("run failed: exception <{}>, event was <{}>".format(decide_exception_msg, decided_event.summary))
            elif self.baseclass_logs_summary:
                logger.critical("run failed: stdout {}, stderr {}, exitcode {}, event {}".format(stdout if stdout else "", stderr if stderr else "", exit_code, decided_event.summary))
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

