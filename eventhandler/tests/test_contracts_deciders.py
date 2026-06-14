"""
Contract tests for eventhandler deciders.

This file covers the boundary branches of default and omd_site_self_heal deciders.
"""
import logging
import os
import shutil
import sys
from types import SimpleNamespace

import pytest

os.environ["PYTHONDONTWRITEBYTECODE"] = "true"

OMD_ROOT = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = OMD_ROOT

if not [p for p in sys.path if "pythonpath" in p]:
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/local/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/pythonpath/lib/python")
    sys.path.append(os.environ["OMD_ROOT"] + "/../../notificationforwarder/src")
    sys.path.append(os.environ["OMD_ROOT"] + "/../src")

from eventhandler import baseclass
from eventhandler.baseclass import DecidedEvent
from eventhandler.default.decider import DefaultDecider
from eventhandler.omd_site_self_heal.decider import OmdSiteSelfHealDecider


def _setup():
    omd_root = os.path.dirname(__file__)
    os.environ["OMD_ROOT"] = omd_root
    shutil.rmtree(omd_root + "/var", ignore_errors=True)
    os.makedirs(omd_root + "/var/log", 0o755)
    os.makedirs(omd_root + "/var/tmp", 0o755)
    shutil.rmtree(omd_root + "/tmp", ignore_errors=True)
    os.makedirs(omd_root + "/tmp", 0o755)


@pytest.fixture
def setup():
    _setup()
    yield


def _new_runner(runner_name, decider_name="example", runner_opts=None, logger_type="text"):
    return baseclass.new(
        runner_name,
        None,
        decider_name,
        True,
        True,
        runner_opts or {},
        logger_type=logger_type,
    )


def _decided_event(eventopts):
    return DecidedEvent(dict(eventopts))


# ============================================================================
# Default decider tests
# ============================================================================

class TestDefaultDecider:
    def test_host_downtime_discard(self, setup):
        """Default decider discards loudly on HOSTDOWNTIME=True."""
        decider = DefaultDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "HOSTDOWNTIME": True,
            "SERVICEDOWNTIME": False,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is True
        assert event.is_discarded_silently is False
        assert "downtime" in event.summary.lower()

    def test_service_downtime_discard(self, setup):
        """Default decider discards loudly on SERVICEDOWNTIME=True."""
        decider = DefaultDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": True,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is True
        assert event.is_discarded_silently is False

    def test_attempt_2_discard(self, setup):
        """Default discards loudly when SERVICEATTEMPT=2 on non-OK."""
        decider = DefaultDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 2,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is True
        assert event.is_discarded_silently is False
        assert "did not help" in event.summary.lower()

    def test_attempt_3_silent_discard(self, setup):
        """Default discards silently when SERVICEATTEMPT=3."""
        decider = DefaultDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 3,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is True
        assert event.is_discarded_silently is True

    def test_attempt_1_proceeds(self, setup):
        """Default allows event to proceed when SERVICEATTEMPT=1, non-OK, no downtime."""
        decider = DefaultDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is False
        assert event.payload is not None


# ============================================================================
# omd_site_self_heal decider tests
# ============================================================================

class TestOmdSiteSelfHealDecider:
    def test_host_downtime_discard(self, setup):
        """OMD decider discards loudly on HOSTDOWNTIME=True."""
        decider = OmdSiteSelfHealDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "site_name": "site1",
            "HOSTDOWNTIME": True,
            "SERVICEDOWNTIME": False,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is True
        assert event.is_discarded_silently is False

    def test_service_downtime_discard(self, setup):
        """OMD decider discards loudly on SERVICEDOWNTIME=True."""
        decider = OmdSiteSelfHealDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "site_name": "site1",
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": True,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is True
        assert event.is_discarded_silently is False

    def test_attempt_2_discard(self, setup):
        """OMD decider discards loudly when SERVICEATTEMPT=2."""
        decider = OmdSiteSelfHealDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "site_name": "site1",
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 2,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is True
        assert event.is_discarded_silently is False

    def test_attempt_3_loud_discard(self, setup):
        """OMD decider discards LOUDLY when SERVICEATTEMPT=3 (differs from default)."""
        decider = OmdSiteSelfHealDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "site_name": "site1",
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 3,
        })

        decider.decide_and_prepare(event)

        # OMD decider uses loud discard for attempt=3 (differs from default)
        assert event.is_discarded is True
        assert event.is_discarded_silently is False

    def test_attempt_1_payload(self, setup):
        """OMD decider sets user=site and check_omd --heal command on attempt=1."""
        decider = OmdSiteSelfHealDecider()

        event = _decided_event({
            "HOSTNAME": "h1",
            "SERVICEDESC": "svc",
            "site_name": "mysite",
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is False
        assert event.payload["user"] == "mysite"
        assert "check_omd" in event.payload["command"]
        assert "--heal" in event.payload["command"]


# ============================================================================
# Own-module contract smoke tests (agent templates)
# ============================================================================
# AI-AGENT TEMPLATE: when a user says "I need a decider for Ticket System XY",
# copy this structure, replace the external mock, keep the contract assertions.

class TestOwnDeciderSmoke:
    def test_own_decider_sets_payload_and_summary(self, setup):
        """
        AI-AGENT TEMPLATE: Own decider contract smoke.
        When implementing a new decider, decide_and_prepare() must set both
        event.payload (dict with data for the runner) and event.summary
        (human-readable string). If the event should be discarded, call
        event.discard(silently=...).
        """
        from eventhandler.example.decider import ExampleDecider

        decider = ExampleDecider()
        event = _decided_event({
            "HOSTNAME": "myhost",
            "SERVICEDESC": "myservice",
            "SERVICESTATE": "CRITICAL",
            "SERVICEATTEMPT": 1,
            "HOSTDOWNTIME": False,
            "SERVICEDOWNTIME": False,
            "content": "test payload",
            "summary": "test summary",
        })

        decider.decide_and_prepare(event)

        # Contract: payload must be a dict
        assert isinstance(event.payload, dict)
        # Contract: summary must be a non-empty string
        assert isinstance(event.summary, str)
        assert len(event.summary) > 0
        # Contract: payload contains the content
        assert event.payload["content"] == "test payload"

    def test_own_decider_discard(self, setup):
        """
        AI-AGENT TEMPLATE: Own discard path.
        When a decider decides to discard, call event.discard(silently=True/False).
        """
        from eventhandler.example.decider import ExampleDecider

        decider = ExampleDecider()
        event = _decided_event({
            "HOSTNAME": "myhost",
            "content": "test payload",
            "discard": True,
        })

        decider.decide_and_prepare(event)

        assert event.is_discarded is True
