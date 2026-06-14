"""
Loading and resolution layer tests for notificationforwarder.

Covers component_loader.resolve_component, load_forwarder, load_formatter,
and load_application_logger using the pythonpath fixture trees.
"""
import logging
import os
import sys

import pytest

os.environ["PYTHONDONTWRITEBYTECODE"] = "true"

OMD_ROOT = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = OMD_ROOT

if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.insert(0, os.environ["OMD_ROOT"] + "/pythonpath/local/lib/python")
    sys.path.insert(0, os.environ["OMD_ROOT"] + "/pythonpath/lib/python")

from notificationforwarder.component_loader import (
    ComponentLoadError,
    load_application_logger,
    load_formatter,
    load_forwarder,
    resolve_component,
)


def _setup():
    omd_root = os.path.dirname(__file__)
    os.environ["OMD_ROOT"] = omd_root


@pytest.fixture
def setup():
    _setup()
    yield


# ============================================================================
# resolve_component
# ============================================================================

class TestResolveComponent:
    def test_derived_naming_underscore(self):
        """underscore_name + suffix → CamelCase + suffix"""
        module_name, class_name, rule = resolve_component("my_thing", "Forwarder")
        assert module_name == "my_thing"
        assert class_name == "MyThingForwarder"
        assert rule == "derived-class"

    def test_derived_naming_simple(self):
        """simple_name + suffix → SimpleName + suffix"""
        module_name, class_name, rule = resolve_component("webhook", "Formatter")
        assert module_name == "webhook"
        assert class_name == "WebhookFormatter"
        assert rule == "derived-class"

    def test_explicit_dotted_name(self):
        """explicit.module.ClassName → module, ClassName, explicit-class"""
        module_name, class_name, rule = resolve_component(
            "my.module.MyClass", "Forwarder"
        )
        assert module_name == "my.module"
        assert class_name == "MyClass"
        assert rule == "explicit-class"

    def test_explicit_dotted_preserves_class(self):
        """Explicit class name is not modified"""
        module_name, class_name, rule = resolve_component(
            "some.lib.CustomFormatter", "Formatter"
        )
        assert class_name == "CustomFormatter"

    def test_single_word(self):
        """single word without underscore"""
        module_name, class_name, rule = resolve_component("syslog", "Forwarder")
        assert module_name == "syslog"
        assert class_name == "SyslogForwarder"


# ============================================================================
# load_forwarder via pythonpath
# ============================================================================

class TestLoadForwarder:
    def test_loads_from_pythonpath(self, setup):
        """split1/forwarder loads from pythonpath/lib/python"""
        app_logger = logging.getLogger("test_load_forwarder")
        _mod, cls, instance, details = load_forwarder(
            "split1", {"username": "u", "password": "p"}, app_logger
        )
        assert cls.__name__ == "Split1Forwarder"
        assert instance.__module_file__.endswith(
            "pythonpath/lib/python/notificationforwarder/split1/forwarder.py"
        )

    def test_local_overrides_lib(self, setup):
        """split2 local forwarder overrides lib forwarder"""
        app_logger = logging.getLogger("test_load_forwarder")
        _mod, cls, instance, details = load_forwarder(
            "split2", {"url": "http://example.invalid"}, app_logger
        )
        # local/lib/python has split2/forwarder.py, should take precedence
        assert cls.__name__ == "Split2Forwarder"

    def test_missing_forwarder_raises(self, setup):
        """Missing forwarder module raises ComponentLoadError"""
        app_logger = logging.getLogger("test_load_forwarder")
        with pytest.raises(ComponentLoadError) as exc_info:
            load_forwarder("nonexistent_forwarder", {}, app_logger)
        assert "could not load forwarder" in str(exc_info.value)

    def test_details_include_component_name(self, setup):
        """ComponentLoadError.details contains component_name"""
        app_logger = logging.getLogger("test_load_forwarder")
        with pytest.raises(ComponentLoadError) as exc_info:
            load_forwarder("missing_one", {}, app_logger)
        assert exc_info.value.details["component_name"] == "missing_one"
        assert exc_info.value.details["component_type"] == "forwarder"


# ============================================================================
# load_formatter via pythonpath
# ============================================================================

class TestLoadFormatter:
    def test_loads_from_pythonpath(self, setup):
        """vong/formatter loads from pythonpath/local/lib/python"""
        app_logger = logging.getLogger("test_load_formatter")
        instance, details = load_formatter("vong", app_logger)
        assert instance.__class__.__name__ == "VongFormatter"
        assert instance.__module_file__.endswith(
            "pythonpath/local/lib/python/notificationforwarder/vong/formatter.py"
        )

    def test_missing_formatter_raises(self, setup):
        """Missing formatter module raises ComponentLoadError"""
        app_logger = logging.getLogger("test_load_formatter")
        with pytest.raises(ComponentLoadError) as exc_info:
            load_formatter("nonexistent_formatter", app_logger)
        assert "could not load formatter" in str(exc_info.value)

    def test_details_include_resolution_rule(self, setup):
        """ComponentLoadError.details includes resolution_rule"""
        app_logger = logging.getLogger("test_load_formatter")
        with pytest.raises(ComponentLoadError) as exc_info:
            load_formatter("missing_fmt", app_logger)
        assert exc_info.value.details["resolution_rule"] == "derived-class"


# ============================================================================
# load_application_logger fallback
# ============================================================================

class TestLoadApplicationLogger:
    def test_valid_logger_type(self, setup):
        """Valid logger type returns correct class"""
        logger = logging.getLogger("test_app_logger")
        instance = load_application_logger("text", "test", logger)
        assert instance.__class__.__name__ == "TextLogger"

    def test_invalid_type_falls_back_to_text(self, setup):
        """Invalid logger type falls back to TextLogger"""
        logger = logging.getLogger("test_app_logger")
        instance = load_application_logger("nonexistent_logger", "test", logger)
        assert instance.__class__.__name__ == "TextLogger"
