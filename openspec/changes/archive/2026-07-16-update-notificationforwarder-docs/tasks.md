## 1. Flush, Probe, and Heartbeat Documentation in README.md

- [x] 1.1 Add a "Spool Flushing" section after the Reporters section in README.md, explaining that every event triggers the flush phase in `forward_formatted()` and that this attempts to re-submit previously spooled events
- [x] 1.2 Add a "Probe Method" subsection explaining the three scenarios: probe() returns True (flush proceeds), probe() returns False (flush skipped), no probe() method (flush proceeds anyway)
- [x] 1.3 Add a "Heartbeat Events" subsection explaining that formatters set `event.is_heartbeat = True`, that heartbeats skip spooling on failure, and that their unique value is guaranteed flush frequency in healthy systems
- [x] 1.4 Add a "Scheduling Heartbeats in Nagios/Naemon" subsection with a concrete command definition (NOTIFICATIONTYPE=HEARTBEAT), a service definition (check_interval, notification_options n, notification_interval 0), and an explanation that the service always exits OK and is used as a scheduler

## 2. Nostr Section in INDEX.md

- [x] 2.1 Copy the Nostr section from README.md (lines 246-272) into INDEX.md, placing it after the SyslogForwarder section and before the Loggers section

## 3. Flush, Probe, and Heartbeat Documentation in INDEX.md

- [x] 3.1 Add the same Spool Flushing, Probe Method, Heartbeat Events, and Nagios scheduling sections to INDEX.md, matching the content added to README.md in tasks 1.1-1.4
