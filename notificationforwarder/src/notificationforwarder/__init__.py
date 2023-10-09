import os
import pkgutil
__path__ = pkgutil.extend_path(__path__, __name__)
from importlib import import_module
from importlib.util import find_spec, module_from_spec
from .baseclass import NotificationForwarder
import logging
from coshsh.util import setup_logging

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
        logger_name = "notificationforwarder_"+tag+"_"+target_name
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
        instance.name = target_name
        # so we can use logger.info(...) in the single modules
        forwarder_module.logger = logging.getLogger(logger_name)
        base_module = import_module('.baseclass', package='notificationforwarder')
        base_module.logger = logging.getLogger(logger_name)

    #except (AttributeError, ModuleNotFoundError):
    except Exception as e:
        #print(e)
        raise ImportError('{} is not part of our forwarder collection!'.format(target_name))
    else:
        if not issubclass(forwarder_class, NotificationForwarder):
            raise ImportError("We currently don't have {}, but you are welcome to send in the request for it!".format(forwarder_class))

    return instance


