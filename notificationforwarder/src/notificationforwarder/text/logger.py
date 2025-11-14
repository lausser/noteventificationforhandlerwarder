#!/usr/bin/env python
# -*- coding: utf-8 -*-

from notificationforwarder.baseclass import NotificationLogger
import sys


class TextLogger(NotificationLogger):
    """
    Text logger - maintains backward compatibility with existing log format

    Format: %(asctime)s %(process)d - %(levelname)s - %(message)s
    """

    def log(self, level, message, context=None):
        """
        Log in text format

        Args:
            level: Log level string
            message: Base message
            context: Structured context dict
        """
        if context is None:
            context = {}

        # Build enhanced message with context
        full_message = self._build_message(message, context)

        # Get log function
        log_func = getattr(self.python_logger, level.lower())

        # Log with exception info if present
        if 'exc_info' in context and context['exc_info']:
            log_func(full_message, exc_info=context['exc_info'])
        else:
            log_func(full_message)

    def _build_message(self, message, context):
        """
        Build text log message from structured context

        Maintains backward compatibility with existing log format
        """
        parts = [message]

        # Add exception info
        if 'exception' in context and context['exception']:
            exc = context['exception']
            if isinstance(exc, Exception):
                parts.append(f"with exception <{str(exc)}>")
            else:
                parts.append(f"with exception <{exc}>")

        # Add spooled event info
        if context.get('spooled') and 'formatted_event' in context:
            event = context['formatted_event']
            if hasattr(event, 'summary') and event.summary:
                parts.append(f", spooled <{event.summary}>")

        # Add formatted event summary for success/discard messages
        if 'formatted_event' in context and not context.get('spooled'):
            event = context['formatted_event']
            if hasattr(event, 'summary') and event.summary:
                # For messages like "forwarded" or "discarded", append the summary
                if message in ["forwarded", "discarded"]:
                    parts.append(event.summary)

        # Add raw event for certain error messages
        if 'raw_event' in context and message.startswith("raw event"):
            parts.append(f"caused error {context.get('exception', 'unknown')}")

        # Add formatter info for formatting errors
        if 'event_data' in context and 'formatter_instance' in context:
            fmt = context['formatter_instance']
            parts = [f"when formatting this {context['event_data']} with this {fmt.__class__.__name__}@{fmt.__module_file__} there was an error <{context.get('exception', '')}>"]

        # Add reporter info for reporting errors
        if 'reporter_instance' in context and message.startswith("when reporting"):
            rpt = context['reporter_instance']
            event_opts = context.get('event_data', {})
            parts = [f"when reporting this {event_opts} with this {rpt.__class__.__name__}@{rpt.__module_file__} there was an error <{context.get('exception', '')}>"]

        # Add reporter creation error
        if 'reporter_name' in context and message.startswith("could not create"):
            parts = [f"could not create a {context['reporter_name']} reporter instance with {context.get('reporter_opts', {})}"]

        # Handle split events message
        if 'split_count' in context:
            return f"received a payload with {context['split_count']} single events"

        # Handle split events error
        if 'split_error' in context and 'raw_event' in context:
            return f"error split_events failed for {context['raw_event']}"

        # Handle spooled count messages
        if 'spooled_count' in context and 'action' in context:
            action = context['action']
            count = context['spooled_count']
            if action == 'resend':
                return f"there are {count} spooled events to be re-sent"
            elif action == 'dropped':
                return f"dropped {count} outdated events"
            elif action == 'could_not_submit':
                return f"{count} spooled events could not be submitted"
            elif action == 'delete':
                return f"delete spooled event {context.get('event_id', '')}"
            elif action == 'stays_in_spool':
                return f"event {context.get('event_id', '')} stays in spool"
            elif action == 'delete_trash':
                return f"delete trash event {context.get('event_id', '')}"
            elif action == 'could_not_format':
                return f"could not format spooled {context.get('raw_event', '')}. sorry, but i will delete this garbage with id {context.get('event_id', '')}"

        # Add queue length warnings
        if 'queue_length' in context:
            return f"spooling queue length is {context['queue_length']}"

        # Handle database errors
        if 'database_error' in context:
            return f"database error {context['exception']}"

        # Handle flush messages
        if message == "nothing left to flush":
            return message

        if message == "flush probe failed":
            return f"flush probe failed with exception <{context.get('exception', '')}>"

        if message == "database flush+resubmit failed":
            return f"database flush+resubmit failed: {context.get('exception', '')}"

        if message == "flush lock set":
            return "flush lock set"

        if message == "flush lock failed":
            return f"flush lock failed (attempt {context.get('attempt', 'unknown')}): {context.get('exception', '')}"

        if message == "missed the flush lock":
            return "missed the flush lock"

        # Handle db init error
        if message == "error initializing database":
            return f"error initializing database {context.get('db_file', '')}: {context.get('exception', '')}"

        # Handle formatter/forwarder not found
        if message == "found no formatter module":
            return f"found no formatter module {context.get('module_name', '')}"

        if message == "found no reporter module":
            return f"found no reporter module {context.get('module_name', '')}"

        if message == "unknown error in formatter instantiation":
            return f"unknown error error in formatter instantiation: {context.get('exception', '')}"

        if message == "unknown error in reporter instantiation":
            return f"unknown error error in reporter instantiation: {context.get('exception', '')}"

        # Handle incomplete formatted event
        if message == "formatted event incomplete":
            return f"a formatted event {context.get('event_class', 'FormattedEvent')} must have the attributes payload and summary"

        return " ".join(parts)
