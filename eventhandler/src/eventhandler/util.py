import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def setup_logging(logdir=".", logfile="eventhandler.log", scrnloglevel=logging.INFO, txtloglevel=logging.INFO, format="%(asctime)s %(process)d - %(levelname)s - %(message)s", backup_count=3):
    logdir_path = Path(logdir)
    logdir_path.mkdir(parents=True, exist_ok=True)

    logfile_path = Path(logfile)
    abs_logfile = logfile_path if logfile_path.is_absolute() else logdir_path / logfile_path
    abs_logfile.touch(exist_ok=True)
    logger_name = abs_logfile.name[:-4] if abs_logfile.name.endswith(".log") else abs_logfile.name
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter(format)

    file_handler = RotatingFileHandler(str(abs_logfile), maxBytes=20 * 1024 * 1024, backupCount=backup_count, delay=True)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(txtloglevel)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(scrnloglevel)
    logger.addHandler(console_handler)

    logger.debug("Logger initialized.")

    return logger
