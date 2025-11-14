#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demonstration script for text vs JSON logging

This script creates sample log files in /tmp to demonstrate the difference
between text and JSON logging formats.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Setup environment
os.environ['OMD_ROOT'] = '/tmp/demo_omd'
os.environ['OMD_SITE'] = 'demo_site'
os.makedirs('/tmp/demo_omd/var/log', exist_ok=True)
os.makedirs('/tmp/demo_omd/var/tmp', exist_ok=True)
os.makedirs('/tmp/demo_omd/tmp', exist_ok=True)

# Add src to path
sys.path.insert(0, 'src')

from notificationforwarder.text.logger import TextLogger
from notificationforwarder.json.logger import JsonLogger
from notificationforwarder.baseclass import FormattedEvent


def setup_file_logger(logger_name, log_file):
    """Setup a Python logger that writes to a file"""
    python_logger = logging.getLogger(logger_name)
    python_logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    python_logger.handlers = []

    # Create file handler
    handler = RotatingFileHandler(
        log_file,
        maxBytes=20*1024*1024,
        backupCount=3
    )
    handler.setLevel(logging.DEBUG)

    # Simple format for text logger, just message for JSON logger
    if 'json' in log_file:
        formatter = logging.Formatter('%(message)s')
    else:
        formatter = logging.Formatter('%(asctime)s %(process)d - %(levelname)s - %(message)s')

    handler.setFormatter(formatter)
    python_logger.addHandler(handler)

    return python_logger


def create_sample_events():
    """Create sample events for demonstration"""
    events = []

    # Event 1: Critical service
    event1_data = {
        'HOSTNAME': 'webserver01.example.com',
        'SERVICEDESC': 'Apache',
        'SERVICESTATE': 'CRITICAL',
        'SERVICEOUTPUT': 'HTTP CRITICAL - Unable to connect to server',
        'NOTIFICATIONTYPE': 'PROBLEM'
    }
    event1 = FormattedEvent(event1_data)
    event1.summary = 'webserver01.example.com/Apache: CRITICAL - Unable to connect'
    events.append(('forward failed', {
        'exception': 'Connection timeout after 30s',
        'formatted_event': event1,
        'spooled': True,
        'forwarder_name': 'webhook',
        'formatter_name': 'json'
    }))

    # Event 2: Warning service
    event2_data = {
        'HOSTNAME': 'dbserver02.example.com',
        'SERVICEDESC': 'MySQL',
        'SERVICESTATE': 'WARNING',
        'SERVICEOUTPUT': 'MySQL WARNING - Slow queries detected',
        'NOTIFICATIONTYPE': 'PROBLEM'
    }
    event2 = FormattedEvent(event2_data)
    event2.summary = 'dbserver02.example.com/MySQL: WARNING - Slow queries'
    events.append(('forwarded', {
        'formatted_event': event2,
        'status': 'success'
    }))

    # Event 3: Recovery
    event3_data = {
        'HOSTNAME': 'mailserver03.example.com',
        'SERVICEDESC': 'SMTP',
        'SERVICESTATE': 'OK',
        'SERVICEOUTPUT': 'SMTP OK - responding normally',
        'NOTIFICATIONTYPE': 'RECOVERY'
    }
    event3 = FormattedEvent(event3_data)
    event3.summary = 'mailserver03.example.com/SMTP: OK - responding normally'
    events.append(('forwarded', {
        'formatted_event': event3,
        'status': 'success'
    }))

    return events


def main():
    """Main demonstration function"""
    print("Creating demonstration log files...")
    print()

    # Setup loggers
    text_log_file = '/tmp/demo_omd/var/log/notificationforwarder_demo_text.log'
    json_log_file = '/tmp/demo_omd/var/log/notificationforwarder_demo_json.log'

    text_python_logger = setup_file_logger('demo_text', text_log_file)
    json_python_logger = setup_file_logger('demo_json', json_log_file)

    text_logger = TextLogger('notificationforwarder_demo_text', text_python_logger)
    json_logger = JsonLogger('notificationforwarder_demo_json', json_python_logger, version='2.9')

    # Create sample events
    events = create_sample_events()

    # Log initialization
    text_logger.info("Logger initialized", {})
    json_logger.info("Logger initialized", {})

    # Log sample events
    for message, context in events:
        level = 'critical' if 'exception' in context else 'info'
        getattr(text_logger, level)(message, context)
        getattr(json_logger, level)(message, context)

    # Log spooling information
    text_logger.warning("spooling queue length", {'queue_length': 5})
    json_logger.warning("spooling queue length", {'queue_length': 5})

    text_logger.info("spooled events to be re-sent", {
        'spooled_count': 3,
        'action': 'resend'
    })
    json_logger.info("spooled events to be re-sent", {
        'spooled_count': 3,
        'action': 'resend'
    })

    # Log database operations
    text_logger.info("dropped outdated events", {
        'spooled_count': 2,
        'action': 'dropped'
    })
    json_logger.info("dropped outdated events", {
        'spooled_count': 2,
        'action': 'dropped'
    })

    # Log errors
    text_logger.critical("found no formatter module", {'module_name': 'custom_formatter'})
    json_logger.critical("found no formatter module", {'module_name': 'custom_formatter'})

    # Log with exception
    try:
        raise RuntimeError("Simulated network error")
    except RuntimeError as e:
        text_logger.critical("when formatting event there was an error", {
            'event_data': str({'HOSTNAME': 'test.example.com'}),
            'exception': e,
            'exc_info': sys.exc_info()
        })
        json_logger.critical("when formatting event there was an error", {
            'event_data': str({'HOSTNAME': 'test.example.com'}),
            'exception': e,
            'exc_info': sys.exc_info()
        })

    # Flush handlers
    for handler in text_python_logger.handlers:
        handler.flush()
    for handler in json_python_logger.handlers:
        handler.flush()

    print(f"✓ Text log file created: {text_log_file}")
    print(f"✓ JSON log file created: {json_log_file}")
    print()
    print("You can view the files with:")
    print(f"  cat {text_log_file}")
    print(f"  cat {json_log_file}")
    print()
    print("Or for formatted JSON output:")
    print(f"  cat {json_log_file} | python3 -m json.tool")


if __name__ == '__main__':
    main()
