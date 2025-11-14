#!/usr/bin/env python
# -*- coding: utf-8 -*-

from notificationforwarder.baseclass import NotificationLogger
import sys
try:
    import simplejson as json
except ImportError:
    import json
import traceback
from datetime import datetime, timezone


class JsonLogger(NotificationLogger):
    """
    JSON logger - outputs structured JSON logs

    Format: Single-line JSON with all context fields
    """

    def __init__(self, logger_name, python_logger, version="2.9"):
        super().__init__(logger_name, python_logger)
        self.version = version

    def log(self, level, message, context=None):
        """
        Log in JSON format

        Args:
            level: Log level string
            message: Base message
            context: Structured context dict
        """
        if context is None:
            context = {}

        # Build JSON structure
        log_entry = self._build_json_entry(level, message, context)

        # Convert to JSON string
        json_line = json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))

        # Get log function and log the JSON string
        log_func = getattr(self.python_logger, level.lower())
        log_func(json_line)

    def _build_json_entry(self, level, message, context):
        """
        Build JSON log entry from structured context

        Returns a dict that will be serialized to JSON
        """
        # Base structure
        log_entry = {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "host_name": self.originating_fqdn,
            "version": self.version,
            "level": level.upper(),
            "logger": self.logger_name,
        }

        # Add OMD site if available
        if self.omd_site:
            log_entry["omd_site"] = self.omd_site

        # Extract event information
        if 'formatted_event' in context:
            self._add_event_info(log_entry, context['formatted_event'])
        elif 'event' in context:
            self._add_raw_event_info(log_entry, context['event'])
        elif 'raw_event' in context:
            self._add_raw_event_info(log_entry, context['raw_event'])

        # Build nested msg structure
        msg_data = {
            "message": message
        }

        # Add exception information
        if 'exception' in context and context['exception']:
            exc = context['exception']
            if isinstance(exc, Exception):
                msg_data["exception"] = {
                    "type": type(exc).__name__,
                    "message": str(exc)
                }
                if 'exc_info' in context and context['exc_info']:
                    try:
                        msg_data["exception"]["trace"] = ''.join(
                            traceback.format_exception(*context['exc_info'])
                        )
                    except:
                        pass
            else:
                msg_data["exception"] = str(exc)

        # Add spooling information
        if context.get('spooled'):
            msg_data["spooled"] = True
            if 'formatted_event' in context:
                event = context['formatted_event']
                if hasattr(event, 'summary'):
                    msg_data["spooled_event"] = event.summary

        # Add operational context
        if 'forwarder_name' in context:
            msg_data["forwarder_name"] = context['forwarder_name']
        if 'formatter_name' in context:
            msg_data["formatter_name"] = context['formatter_name']
        if 'reporter_name' in context:
            msg_data["reporter_name"] = context['reporter_name']

        # Add counts and metrics
        if 'spooled_count' in context:
            msg_data["spooled_count"] = context['spooled_count']
        if 'queue_length' in context:
            msg_data["queue_length"] = context['queue_length']
        if 'dropped_count' in context:
            msg_data["dropped_count"] = context['dropped_count']
        if 'split_count' in context:
            msg_data["split_count"] = context['split_count']
        if 'event_id' in context:
            msg_data["event_id"] = context['event_id']

        # Add action type
        if 'action' in context:
            msg_data["action"] = context['action']

        # Add formatter/reporter instance info for errors
        if 'formatter_instance' in context:
            fmt = context['formatter_instance']
            msg_data["formatter_class"] = fmt.__class__.__name__
            msg_data["formatter_module"] = fmt.__module_file__

        if 'reporter_instance' in context:
            rpt = context['reporter_instance']
            msg_data["reporter_class"] = rpt.__class__.__name__
            msg_data["reporter_module"] = rpt.__module_file__

        # Add event data for errors
        if 'event_data' in context:
            msg_data["event_data"] = context['event_data']

        # Add status indicators
        if context.get('status'):
            msg_data["status"] = context['status']

        # Add database info
        if 'db_file' in context:
            msg_data["db_file"] = context['db_file']
        if 'database_error' in context:
            msg_data["database_error"] = True

        # Add module name for not found errors
        if 'module_name' in context:
            msg_data["module_name"] = context['module_name']

        # Add event class for incomplete events
        if 'event_class' in context:
            msg_data["event_class"] = context['event_class']

        # Add attempt number for retry operations
        if 'attempt' in context:
            msg_data["attempt"] = context['attempt']

        # Add reporter opts
        if 'reporter_opts' in context:
            msg_data["reporter_opts"] = context['reporter_opts']

        log_entry["msg"] = msg_data

        return log_entry

    def _add_event_info(self, log_entry, formatted_event):
        """Extract event information from FormattedEvent"""
        if not formatted_event:
            return

        eventopts = getattr(formatted_event, 'eventopts', {})

        # Extract key event fields
        if 'HOSTNAME' in eventopts:
            log_entry["event_host_name"] = eventopts['HOSTNAME']
        if 'SERVICEDESC' in eventopts:
            log_entry["event_service_name"] = eventopts['SERVICEDESC']
        if 'SERVICESTATE' in eventopts:
            log_entry["event_state"] = eventopts['SERVICESTATE']
        elif 'HOSTSTATE' in eventopts:
            log_entry["event_state"] = eventopts['HOSTSTATE']
        if 'NOTIFICATIONTYPE' in eventopts:
            log_entry["event_notification_type"] = eventopts['NOTIFICATIONTYPE']

        # Add service/host output
        if 'SERVICEOUTPUT' in eventopts:
            log_entry["event_service_output"] = eventopts['SERVICEOUTPUT']
        elif 'HOSTOUTPUT' in eventopts:
            log_entry["event_host_output"] = eventopts['HOSTOUTPUT']

        # Add event summary
        if hasattr(formatted_event, 'summary') and formatted_event.summary:
            log_entry["event_summary"] = formatted_event.summary

        # Add timestamp if available
        if 'omd_originating_timestamp' in eventopts:
            log_entry["event_timestamp"] = eventopts['omd_originating_timestamp']

    def _add_raw_event_info(self, log_entry, raw_event):
        """Extract event information from raw event dict"""
        if not raw_event or not isinstance(raw_event, dict):
            return

        if 'HOSTNAME' in raw_event:
            log_entry["event_host_name"] = raw_event['HOSTNAME']
        if 'SERVICEDESC' in raw_event:
            log_entry["event_service_name"] = raw_event['SERVICEDESC']
        if 'SERVICESTATE' in raw_event:
            log_entry["event_state"] = raw_event['SERVICESTATE']
        elif 'HOSTSTATE' in raw_event:
            log_entry["event_state"] = raw_event['HOSTSTATE']
        if 'NOTIFICATIONTYPE' in raw_event:
            log_entry["event_notification_type"] = raw_event['NOTIFICATIONTYPE']

        # Add service/host output
        if 'SERVICEOUTPUT' in raw_event:
            log_entry["event_service_output"] = raw_event['SERVICEOUTPUT']
        elif 'HOSTOUTPUT' in raw_event:
            log_entry["event_host_output"] = raw_event['HOSTOUTPUT']

        if 'omd_originating_timestamp' in raw_event:
            log_entry["event_timestamp"] = raw_event['omd_originating_timestamp']
