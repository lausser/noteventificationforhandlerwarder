import os
import re
import socket
import time


def enrich_raw_event(raw_event):
    if "omd_site" not in raw_event:
        raw_event["omd_site"] = os.environ.get("OMD_SITE", "get https://omd.consol.de/docs/omd")
    raw_event["omd_originating_host"] = socket.gethostname()
    raw_event["omd_originating_fqdn"] = socket.getfqdn()
    raw_event["omd_originating_timestamp"] = int(time.time())

    empty_macros = []
    for macro in raw_event:
        if isinstance(raw_event[macro], dict) or isinstance(raw_event[macro], list):
            continue
        raw_event[macro] = str(raw_event[macro])
        if raw_event[macro] == "$":
            empty_macros.append(macro)
        elif re.search(r"^\$\w+\$", raw_event[macro]):
            empty_macros.append(macro)
    for macro in empty_macros:
        del raw_event[macro]
    return raw_event


def apply_forward_result(result):
    report_payload = {}
    error_message = None
    if isinstance(result, bool):
        return result, report_payload, error_message
    if isinstance(result, dict):
        success = result.get("success", False)
        report_payload = result.get("report_payload", {})
        error_message = result.get("error_message")
        return success, report_payload, error_message
    return False, report_payload, error_message


def add_reporter_event_context(formatted_event, forwarder_name, formatter_name, success, report_payload, forwarder_tag=""):
    formatted_event.eventopts["forwarder_name"] = forwarder_name
    formatted_event.eventopts["forwarder_tag"] = forwarder_tag
    formatted_event.eventopts["forwarder_success"] = success
    formatted_event.eventopts["formatter_name"] = formatter_name
    formatted_event.eventopts["formatter_summary"] = formatted_event.summary
    if report_payload:
        formatted_event.eventopts["forwarder_report_payload"] = report_payload
