# eventhandler

The eventhandler framework provides a flexible system for executing automated actions in response to monitoring events. Similar to notificationforwarder, it uses a modular architecture with *runners*, *deciders*, and *formatters* to handle event-driven automation tasks.

## Loggers

The framework uses a modular logging architecture similar to runners, deciders, and formatters. By default, eventhandler uses **text format logging** - you don't need to do anything, logging works exactly as it did before. The traditional text format is backward compatible with all existing installations.

### Why JSON Logging?

In enterprise environments, the gateway from monitoring systems to incident management platforms like Remedy, ServiceNow, or other ITSM tools is crucial for operational reliability. For comprehensive monitoring and troubleshooting of this critical path, logs need to be ingested into log aggregation systems like Splunk for analysis, alerting, and correlation.

The JSON logger provides structured logging optimized for ingestion into Splunk and other log management systems. It outputs single-line JSON with:
- Splunk-friendly underscore field naming (e.g., `event_host_name`, `event_service_name`)
- Complete event details including state, output, and summary
- Operational metrics and execution details
- Structured exception traces
- Timezone-aware timestamps

### Usage

**Default (text logging):**
```bash
$USER1$/eventhandler \
    --runner ssh \
    --decider default \
    --eventopt HOSTNAME='$HOSTNAME$' \
    --eventopt SERVICESTATE='$SERVICESTATE$'
```

**JSON logging for Splunk ingestion:**
```bash
$USER1$/eventhandler \
    --runner ssh \
    --decider default \
    --logger json \
    --eventopt HOSTNAME='$HOSTNAME$' \
    --eventopt SERVICESTATE='$SERVICESTATE$'
```

**Custom logger:**
```bash
$USER1$/eventhandler \
    --runner ssh \
    --logger mycustomlogger \
    --eventopt HOSTNAME='$HOSTNAME$'
```

### Example Log Output

**Text format (default):**
```
2025-11-13 17:00:57,987 3468977 - INFO - executed action for dbserver02.example.com/MySQL: WARNING - Slow queries
```

**JSON format:**
```json
{
  "timestamp": "2025-11-13T17:00:57.987487+01:00",
  "host_name": "oasch.example.com",
  "version": "2.9",
  "level": "INFO",
  "logger": "eventhandler_ssh",
  "omd_site": "demo_site",
  "event_host_name": "dbserver02.example.com",
  "event_service_name": "MySQL",
  "event_state": "WARNING",
  "event_notification_type": "PROBLEM",
  "event_service_output": "MySQL WARNING - Slow queries detected",
  "event_summary": "dbserver02.example.com/MySQL: WARNING - Slow queries",
  "msg": {
    "message": "executed action",
    "status": "success"
  }
}
```

### Custom Loggers

You can create custom loggers by:
1. Creating `~/local/lib/python/eventhandler/mylogger/logger.py`
2. Inheriting from `EventhandlerLogger` base class
3. Implementing the `log(level, message, context)` method

```python
from eventhandler.baseclass import EventhandlerLogger

class MyloggerLogger(EventhandlerLogger):
    def log(self, level, message, context=None):
        # Custom logging implementation
        pass
```
