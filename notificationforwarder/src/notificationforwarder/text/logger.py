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

    def _spool_event_line(self, lead, context):
        """Render a line which names a spool entry.

        The lead already contains the event id. The summary is appended when
        the context carries one, the raw event is the payload stored in the
        spool, and the submit error ends the line when it exists."""
        description = [lead]
        if context.get('summary'):
            description.append(f"summary <{context['summary']}>")
        if 'raw_event' in context:
            description.append(f"raw event <{context['raw_event']}>")
        exception = context.get('exception')
        if exception:
            description.append(f"with exception <{exception}>")
        if 'payload_text' in context:
            description.append(f"payload <{context['payload_text']}>")
        return " ".join(description)

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

        # The spool-time line for a failed delivery which was spooled:
        # names the spool row id, the stored raw event and the summary
        if message == "forward failed" and 'event_id' in context and 'raw_event' in context:
            return self._spool_event_line(
                f"forward failed, spool id {context['event_id']}", context)

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
            message = f"error split_events failed for {context['raw_event']}"
            exception = context.get('exception')
            if exception:
                message += f" with exception <{exception}>"
            return message

        # Handle a rejected spooled event which was moved behind the others
        if context.get('action') == 'moved_to_end':
            return (f"event {context.get('event_id', '')} was rejected while the receiver accepts "
                    f"other events and moved to the end of the spool as {context.get('new_event_id', '')}")

        # Handle action-typed spool operations. The counting operations carry
        # a spooled_count, the per-event lines describe one spooled row each
        # with id, summary (when one exists) and raw event.
        if 'action' in context:
            action = context['action']
            count = context.get('spooled_count')
            event_id = context.get('event_id', '')
            if action == 'resend':
                return f"there are {count} spooled events to be re-sent"
            elif action == 'dropped':
                return f"dropped {count} outdated events"
            elif action == 'could_not_submit':
                return f"{count} spooled events could not be submitted"
            elif action == 'delete':
                return self._spool_event_line(f"delete spooled event {event_id}", context)
            elif action == 'stays_in_spool':
                return self._spool_event_line(f"event {event_id} stays in spool", context)
            elif action == 'delete_trash':
                return self._spool_event_line(f"delete trash event {event_id}", context)
            elif action == 'discard_during_replay':
                return self._spool_event_line(
                    f"discard spooled event during replay {event_id}", context)
            elif action == 'expired':
                return self._spool_event_line(
                    f"expired spooled event {event_id}", context)
            elif action == 'expired_undecodable':
                return (f"expired spool entry {event_id} could not be decoded, "
                        f"payload <{context.get('payload_text', '')}> with exception <{context.get('exception', '')}>")
            elif action == 'could_not_format':
                return (f"could not format spooled {context.get('raw_event', '')}. "
                        f"sorry, but i will delete this garbage with id {event_id}")

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

        if message == "concurrent flush suppressed":
            return "concurrent flush suppressed"

        if message == "spool replay summary":
            return (
                "spool replay summary: attempted={attempted}, recovered={recovered}, "
                "stayed_in_spool={stayed}, deleted_trash={trash}, dropped={dropped}"
            ).format(
                attempted=context.get('attempted', 0),
                recovered=context.get('recovered_count', 0),
                stayed=context.get('stays_in_spool_count', 0),
                trash=context.get('deleted_trash_count', 0),
                dropped=context.get('dropped_count', 0),
            )

        # Handle db init error
        if message == "error initializing database":
            return f"error initializing database {context.get('db_file', '')}: {context.get('exception', '')}"

        if message == "delivery failed and event could not be persisted":
            event = context.get('formatted_event')
            summary = getattr(event, 'summary', None)
            suffix = f" <{summary}>" if summary else ""
            if context.get('exception'):
                return f"delivery failed and event could not be persisted{suffix} with exception <{context.get('exception')}>"
            return f"delivery failed and event could not be persisted{suffix}"

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
