#! /usr/bin/python3

import argparse
import logging
import logging.handlers
import os
import sys
sys.dont_write_bytecode = True
from coshsh.util import setup_logging
import eventhandler
import notificationforwarder
import traceback


if __name__ == '__main__':
    VERSION = "1.0"

    if not os.environ.get("OMD_ROOT", "").startswith("/omd/sites/") and os.environ.get("OMD_SITE", "") != "my_devel_site"):
        print("This script must be run in an OMD environment")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description="run event handler commands")
    parser.add_argument('--livestatus', action='store',
                      dest="livestatus",
                      help='The livestatus port')
    parser.add_argument('--handler', action='store',
                      dest="handler",
                      help='''The type of script.
This can be any backend you want, provided
there is a Python module <backend>.py in the folder
eventhandler somewhere in your PYTHONPATH.
Examples are ssh, nsc_web,...''',
                      default="ssh")
    parser.add_argument('--eventopt', action = type('', (argparse.Action, ),
        dict(__call__ = lambda a, p, n, v, o:
            getattr(n, a.dest).update(dict([v.split('=', 1)])))), 
                      default = {},
                      help="Naemon runtime attributes")
    parser.add_argument('--handleropt', action = type('', (argparse.Action, ),
        dict(__call__ = lambda a, p, n, v, o:
            getattr(n, a.dest).update(dict([v.split('=', 1)])))),
                      default = {},
                      help="""Handler attributes. These are specific for
the type of backend. Example for NscWeb:
--handleropt password=...
--receiveropt insecure=...""")
    parser.add_argument('--handlertag', action='store',
                      dest="handlertag",
                      help='A distinctive string which is added to the log',
                      default=None)
    parser.add_argument('--receiver', action='store',
                      dest="receiver",
                      help='''The type of recipient.
This can be any backend you want, provided
there is a Python module <backend>.py in the folder
notificationforwarder somewhere in your PYTHONPATH.
Examples are victorops, syslog, servicenow, rabbitmq,...''',
                      default=None)
    parser.add_argument('--receiveropt', action = type('', (argparse.Action, ),
        dict(__call__ = lambda a, p, n, v, o:
            getattr(n, a.dest).update(dict([v.split('=', 1)])))),
                      default = {},
                      help="""Receiver attributes. These are specific for
the type of backend. Example for VictorOps:
--receiveropt company_id=...
--receiveropt routing_key=...
A receiver is optional. If you use one, then the result of an event handler
will be sent to the receiver like an alarm notification.""")
    parser.add_argument('--receivertag', action='store',
                      dest="receivertag",
                      help='A distinctive string which is added to the logfile',
                      default=None)
    parser.add_argument('--verbose', action='store_true',
                      dest="verbose",
                      help='Show logs at stdout',
                      default=False)
    parser.add_argument('--debug', action='store_true',
                      dest="debug",
                      help='Increase the log level to DEBUG',
                      default=False)
    args = parser.parse_args()
    try:
        handler = eventhandler.new(args.handler, args.handlertag, args.verbose, args.debug, args.handleropt)
    except Exception as a:
        logger = logging.getLogger(args.handler)
        traceback.print_exc(file=sys.stdout)
        logger.critical("there is no class for "+args.handler)
        sys.exit(1)
    if args.receiver:
        try:
            handler.forwarder = notificationforwarder.new(args.receiver, args.receivertag, args.verbose, args.debug, args.receiveropt)
        except Exception as a:
            logger = logging.getLogger(args.receiver)
            traceback.print_exc(file=sys.stdout)
            logger.critical("there is no class for "+args.receiver)
    
    handler.handle(args.eventopt)
