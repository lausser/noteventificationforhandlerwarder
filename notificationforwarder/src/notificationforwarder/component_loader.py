from importlib import import_module


class ComponentLoadError(ImportError):
    def __init__(self, message, details):
        super(ComponentLoadError, self).__init__(message)
        self.details = details


def resolve_component(component_name, suffix):
    if "." in component_name:
        module_name, class_name = component_name.rsplit(".", 1)
        resolution_rule = "explicit-class"
    else:
        module_name = component_name
        class_name = "".join(part.title() for part in component_name.split("_")) + suffix
        resolution_rule = "derived-class"
    return module_name, class_name, resolution_rule


def load_application_logger(logger_type, logger_name, python_logger):
    module_name, class_name, resolution_rule = resolve_component(logger_type, "Logger")
    try:
        logger_module = import_module(
            "notificationforwarder." + module_name + ".logger",
            package="notificationforwarder." + module_name,
        )
        logger_class = getattr(logger_module, class_name)
        return logger_class(logger_name, python_logger)
    except Exception as exc:
        from notificationforwarder.text.logger import TextLogger

        fallback_logger = TextLogger(logger_name, python_logger)
        fallback_logger.warning(
            "Could not load logger type, falling back to text",
            {
                "exception": exc,
                "component_name": logger_type,
                "component_type": "logger",
                "module_name": module_name,
                "class_name": class_name,
                "resolution_rule": resolution_rule,
            },
        )
        return fallback_logger


def load_forwarder(target_name, forwarder_opts, app_logger):
    module_name, class_name, resolution_rule = resolve_component(target_name, "Forwarder")
    details = {
        "component_name": target_name,
        "component_type": "forwarder",
        "module_name": module_name,
        "class_name": class_name,
        "resolution_rule": resolution_rule,
    }
    try:
        forwarder_module = import_module(
            "notificationforwarder." + module_name + ".forwarder",
            package="notificationforwarder." + module_name,
        )
        forwarder_module.logger = app_logger
        forwarder_class = getattr(forwarder_module, class_name)
        instance = forwarder_class(forwarder_opts)
        instance.__module_file__ = forwarder_module.__file__
        return forwarder_module, forwarder_class, instance, details
    except Exception as exc:
        details["exception"] = exc
        raise ComponentLoadError("could not load forwarder", details)


def load_formatter(formatter_name, app_logger):
    module_name, class_name, resolution_rule = resolve_component(formatter_name, "Formatter")
    details = {
        "component_name": formatter_name,
        "component_type": "formatter",
        "module_name": module_name,
        "class_name": class_name,
        "resolution_rule": resolution_rule,
    }
    try:
        formatter_module = import_module(
            ".formatter",
            package="notificationforwarder." + module_name,
        )
        formatter_module.logger = app_logger
        formatter_class = getattr(formatter_module, class_name)
        instance = formatter_class()
        instance.__module_file__ = formatter_module.__file__
        return instance, details
    except Exception as exc:
        details["exception"] = exc
        raise ComponentLoadError("could not load formatter", details)


def load_reporter(reporter_name, reporter_opts, app_logger):
    module_name, class_name, resolution_rule = resolve_component(reporter_name, "Reporter")
    details = {
        "component_name": reporter_name,
        "component_type": "reporter",
        "module_name": module_name,
        "class_name": class_name,
        "resolution_rule": resolution_rule,
    }
    try:
        reporter_module = import_module(
            ".reporter",
            package="notificationforwarder." + module_name,
        )
        reporter_module.logger = app_logger
        reporter_class = getattr(reporter_module, class_name)
        instance = reporter_class(reporter_opts)
        instance.__module_file__ = reporter_module.__file__
        return instance, details
    except Exception as exc:
        details["exception"] = exc
        raise ComponentLoadError("could not load reporter", details)
