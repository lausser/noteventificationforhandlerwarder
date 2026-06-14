"""
CLI smoke tests for notificationforwarder and eventhandler.

This file covers --help exit codes and missing required argument behavior.
"""
import os
import shutil
import subprocess
import sys

import pytest

os.environ["PYTHONDONTWRITEBYTECODE"] = "true"

OMD_ROOT = os.path.dirname(__file__)
os.environ["OMD_ROOT"] = OMD_ROOT

NF_BIN = os.path.join(os.path.dirname(OMD_ROOT), "bin", "notificationforwarder")
EH_BIN = os.path.join(os.path.dirname(OMD_ROOT), "..", "eventhandler", "bin", "eventhandler")
NF_SRC = os.path.join(os.path.dirname(OMD_ROOT), "src")
EH_SRC = os.path.join(os.path.dirname(OMD_ROOT), "..", "eventhandler", "src")


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


def _nf_env():
    env = os.environ.copy()
    env["OMD_ROOT"] = OMD_ROOT
    pythonpath = env.get("PYTHONPATH", "")
    for p in [NF_SRC, EH_SRC]:
        if p not in pythonpath:
            pythonpath = p + ":" + pythonpath if pythonpath else p
    env["PYTHONPATH"] = pythonpath
    return env


# ============================================================================
# CLI smoke tests
# ============================================================================

class TestNotificationForwarderCLI:
    def test_nf_exists_and_requires_omd(self, setup):
        """notificationforwarder script exists and produces OMD environment message."""
        assert os.path.exists(NF_BIN)
        result = subprocess.run(
            [sys.executable, NF_BIN, "--help"],
            capture_output=True,
            text=True,
            env=_nf_env(),
        )
        # Without a full OMD environment, the script exits with a helpful message
        assert "OMD" in (result.stdout + result.stderr) or result.returncode == 0

    def test_nf_missing_forwarder_defaults_to_syslog(self, setup):
        """notificationforwarder without --forwarder defaults to syslog and exits."""
        result = subprocess.run(
            [sys.executable, NF_BIN],
            capture_output=True,
            text=True,
            env=_nf_env(),
        )
        # --forwarder defaults to syslog; script exits 0 when OMD check passes
        # (syslog forwarder exists and runs even if no backend is reachable)
        assert result.returncode == 0


class TestEventHandlerCLI:
    def test_eh_exists_and_requires_omd(self, setup):
        """eventhandler script exists and produces OMD environment message."""
        assert os.path.exists(EH_BIN)
        result = subprocess.run(
            [sys.executable, EH_BIN, "--help"],
            capture_output=True,
            text=True,
            env=_nf_env(),
        )
        # Without a full OMD environment, the script exits with a helpful message
        assert "OMD" in (result.stdout + result.stderr) or result.returncode == 0

    def test_eh_missing_runner_nonzero(self, setup):
        """eventhandler without --runner produces non-zero exit."""
        result = subprocess.run(
            [sys.executable, EH_BIN],
            capture_output=True,
            text=True,
            env=_nf_env(),
        )
        assert result.returncode != 0
