import syslog
import logging
from notificationforwarder.baseclass import NotificationForwarder, NotificationFormatter, timeout


class Syslog(NotificationForwarder):
    def __init__(self, opts):
        super(self.__class__, self).__init__(opts)
        setattr(self, "port", int(getattr(self, "port", 514)))
        setattr(self, "server", getattr(self, "server", "localhost"))
        setattr(self, "facility", getattr(self, "facility", "log_local0"))
        setattr(self, "priority", getattr(self, "priority", "info"))
        if self.facility in logging.handlers.SysLogHandler.facility_names:
            self.facility = logging.handlers.SysLogHandler.facility_names[self.facility]
        elif "log_"+self.facility in known_facilities:
            self.facility = logging.handlers.SysLogHandler.facility_names["log_"+self.facility]
        else:
            self.facility = logging.handlers.SysLogHandler.LOG_DAEMON
        if self.priority in logging.handlers.SysLogHandler.priority_names:
            self.priority = logging.handlers.SysLogHandler.priority_names[self.priority]
        elif "log_"+self.priority in logging.handlers.SysLogHandler.priority_names:
            self.priority = logging.handlers.SysLogHandler.priority_names["log_"+self.priority]
        else:
            self.priority = logging.handlers.SysLogHandler.LOG_INFO
        self.syslogger = logging.getLogger('Syslogger')
        # do not suppress anything. (normal logger and syslog have
        # completely different levels. setLevel(NOTSET) does not work.
        self.syslogger.setLevel(-1)
        handler = logging.handlers.SysLogHandler(address=(self.server, self.port), facility=self.facility)
        self.syslogger.addHandler(handler)

    @timeout(30)
    def submit(self, payload):
        try:
            logger.info("submit "+payload)
            self.syslogger.log(self.priority, payload)
            return True
        except Exception as e:
            logger.critical("syslog forwarding had an error: {}".format(str(e)))
            return False


