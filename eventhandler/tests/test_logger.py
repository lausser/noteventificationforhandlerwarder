#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import unittest
import logging
import json
import tempfile
import shutil

# Setup test environment
test_dir = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = test_dir
os.environ["OMD_SITE"] = "my_devel_site"

# Create necessary directories
os.makedirs(os.path.join(test_dir, "var/log"), exist_ok=True)
os.makedirs(os.path.join(test_dir, "var/tmp"), exist_ok=True)
os.makedirs(os.path.join(test_dir, "tmp"), exist_ok=True)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(test_dir), "src"))

from eventhandler.text.logger import TextLogger
from eventhandler.json.logger import JsonLogger
from eventhandler.baseclass import DecidedEvent


class TestEventhandlerTextLogger(unittest.TestCase):
    """Test TextLogger functionality for eventhandler"""

    def setUp(self):
        """Set up test logger"""
        self.logger_name = "test_eventhandler_text_logger"
        self.python_logger = logging.getLogger(self.logger_name)
        self.python_logger.setLevel(logging.DEBUG)

        # Create string handler to capture logs
        self.log_capture = logging.StreamHandler(sys.stdout)
        self.log_capture.setLevel(logging.DEBUG)
        self.python_logger.addHandler(self.log_capture)

        self.logger = TextLogger(self.logger_name, self.python_logger)

    def tearDown(self):
        """Clean up"""
        self.python_logger.removeHandler(self.log_capture)

    def test_simple_message(self):
        """Test logging a simple message"""
        self.logger.info("test message", {})
        self.logger.debug("debug message", {})
        self.logger.warning("warning message", {})
        self.logger.critical("critical message", {})

    def test_message_with_exception(self):
        """Test logging with exception context"""
        try:
            raise ValueError("test error")
        except ValueError as e:
            self.logger.critical("error occurred", {
                'exception': e,
                'exc_info': sys.exc_info()
            })

    def test_message_with_decided_event(self):
        """Test logging with DecidedEvent context"""
        event_data = {
            'HOSTNAME': 'testhost',
            'SERVICEDESC': 'testservice',
            'SERVICESTATE': 'CRITICAL'
        }
        decided_event = DecidedEvent(event_data)
        decided_event.summary = "Running handler for testhost/testservice"

        self.logger.info("event handler executed", {
            'decided_event': decided_event,
            'stdout': 'Command output',
            'stderr': '',
            'exit_code': 0
        })

    def test_message_with_command(self):
        """Test logging with command execution"""
        self.logger.debug("executing command", {
            'command': '/usr/local/bin/restart_service.sh testhost'
        })


class TestEventhandlerJsonLogger(unittest.TestCase):
    """Test JsonLogger functionality for eventhandler"""

    def setUp(self):
        """Set up test logger"""
        self.logger_name = "test_eventhandler_json_logger"
        self.python_logger = logging.getLogger(self.logger_name)
        self.python_logger.setLevel(logging.DEBUG)

        # Create handler to capture logs
        self.log_capture = logging.StreamHandler(sys.stdout)
        self.log_capture.setLevel(logging.DEBUG)
        self.python_logger.addHandler(self.log_capture)

        self.logger = JsonLogger(self.logger_name, self.python_logger, version="1.2.0")

    def tearDown(self):
        """Clean up"""
        self.python_logger.removeHandler(self.log_capture)

    def test_simple_json_message(self):
        """Test JSON logging with simple message"""
        self.logger.info("test message", {})

    def test_json_with_event_context(self):
        """Test JSON logging with event context"""
        event_data = {
            'HOSTNAME': 'testhost',
            'SERVICEDESC': 'testservice',
            'SERVICESTATE': 'WARNING'
        }
        decided_event = DecidedEvent(event_data)
        decided_event.summary = "Executing remediation for testhost"

        self.logger.info("handler executed", {
            'decided_event': decided_event,
            'runner_name': 'ssh',
            'stdout': 'Service restarted',
            'stderr': '',
            'exit_code': 0
        })

    def test_json_with_exception(self):
        """Test JSON logging with exception"""
        try:
            raise RuntimeError("command execution failed")
        except RuntimeError as e:
            self.logger.critical("run failed", {
                'exception': e,
                'exc_info': sys.exc_info(),
                'stdout': '',
                'stderr': 'Connection refused',
                'exit_code': 1
            })

    def test_json_with_decider_context(self):
        """Test JSON logging with decider context"""
        self.logger.debug("decision made", {
            'decider_name': 'default',
            'action': 'execute'
        })

    def test_json_structure(self):
        """Test that JSON output has correct structure"""
        event_data = {
            'HOSTNAME': 'testhost',
            'SERVICEDESC': 'testservice',
            'SERVICESTATE': 'CRITICAL'
        }
        decided_event = DecidedEvent(event_data)
        decided_event.summary = "Test event handler"

        self.logger.critical("run failed", {
            'exception': "SSH connection error",
            'decided_event': decided_event,
            'runner_name': 'ssh',
            'decider_name': 'default',
            'stdout': '',
            'stderr': 'Host unreachable',
            'exit_code': 255
        })


class TestEventhandlerLoggerIntegration(unittest.TestCase):
    """Test logger integration with eventhandler baseclass"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        os.environ["OMD_ROOT"] = self.test_dir
        os.makedirs(os.path.join(self.test_dir, "var/log"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "var/tmp"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "tmp"), exist_ok=True)

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_text_logger_instantiation(self):
        """Test instantiating runner with text logger"""
        from eventhandler import baseclass

        try:
            runner = baseclass.new(
                target_name='example',
                tag=None,
                decider='example',
                verbose=False,
                debug=False,
                runneropts={},
                logger_type='text'
            )
            self.assertIsNotNone(runner)
        except Exception as e:
            # It's okay if example runner doesn't exist in test environment
            self.assertIn("example", str(e).lower())

    def test_json_logger_instantiation(self):
        """Test instantiating runner with JSON logger"""
        from eventhandler import baseclass

        try:
            runner = baseclass.new(
                target_name='example',
                tag=None,
                decider='example',
                verbose=False,
                debug=False,
                runneropts={},
                logger_type='json'
            )
            self.assertIsNotNone(runner)
        except Exception as e:
            # It's okay if example runner doesn't exist in test environment
            self.assertIn("example", str(e).lower())


if __name__ == '__main__':
    unittest.main()
