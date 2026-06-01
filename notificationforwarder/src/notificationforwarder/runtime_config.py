import logging
import os


class RuntimePaths(object):
    def __init__(self, db_file, db_lock_file):
        self.db_file = db_file
        self.db_lock_file = db_lock_file


class RuntimeConfig(object):
    def __init__(
        self,
        target_name,
        tag,
        formatter_name,
        verbose,
        debug,
        forwarder_opts,
        reporter_name=None,
        reporter_opts=None,
        logger_type="text",
        backup_count=3,
        max_spool_minutes=5,
    ):
        self.target_name = target_name
        self.tag = tag
        self.formatter_name = formatter_name
        self.verbose = verbose
        self.debug = debug
        self.forwarder_opts = dict(forwarder_opts or {})
        self.reporter_name = reporter_name
        self.reporter_opts = dict(reporter_opts or {})
        self.logger_type = logger_type
        self.backup_count = backup_count
        self.max_spool_minutes = max_spool_minutes

    @classmethod
    def from_inputs(
        cls,
        target_name,
        tag,
        formatter_name,
        verbose,
        debug,
        forwarder_opts,
        reporter_name=None,
        reporter_opts=None,
        logger_type="text",
    ):
        normalized_forwarder_opts = dict(forwarder_opts or {})
        normalized_reporter_opts = dict(reporter_opts or {})

        if "logfile_backups" in normalized_forwarder_opts:
            backup_count = int(normalized_forwarder_opts.pop("logfile_backups"))
        else:
            backup_count = int(os.environ.get("NOTIFICATIONFORWARDER_LOGFILE_BACKUPS", 3))

        if "max_spool_minutes" in normalized_forwarder_opts:
            max_spool_minutes = int(normalized_forwarder_opts.pop("max_spool_minutes"))
        else:
            max_spool_minutes = int(os.environ.get("NOTIFICATIONFORWARDER_MAX_SPOOL_MINUTES", 5))

        return cls(
            target_name=target_name,
            tag=tag,
            formatter_name=formatter_name,
            verbose=verbose,
            debug=debug,
            forwarder_opts=normalized_forwarder_opts,
            reporter_name=reporter_name,
            reporter_opts=normalized_reporter_opts,
            logger_type=logger_type,
            backup_count=backup_count,
            max_spool_minutes=max_spool_minutes,
        )

    @property
    def forwarder_name(self):
        return self.target_name + ("_" + self.tag if self.tag else "")

    @property
    def logger_name(self):
        return "notificationforwarder_" + self.forwarder_name

    @property
    def screen_log_level(self):
        if self.debug:
            return logging.DEBUG
        if self.verbose:
            return logging.INFO
        return 100

    @property
    def text_log_level(self):
        return logging.DEBUG if self.debug else logging.INFO

    @property
    def omd_root(self):
        return os.environ["OMD_ROOT"]

    @property
    def log_dir(self):
        return self.omd_root + "/var/log"

    def build_paths(self):
        return RuntimePaths(
            db_file=self.omd_root + "/var/tmp/notificationforwarder_" + self.forwarder_name + "_notifications.db",
            db_lock_file=self.omd_root + "/tmp/notificationforwarder" + self.forwarder_name + "_flush.lock",
        )
