"""Committed rejection probe for the focused lint gate.

These tests prove the gate itself works (and that the component-loader
``logger = None`` bindings do not suppress F821), not that the source tree
is style-clean. The authoritative zero-findings proof for the tree is the
pinned CI job (Python 3.12, flake8 7.5.0, ``--config .flake8``).

Requires the ``test`` extra to be installed so that ``python -m flake8``
resolves in the same interpreter pytest runs under.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".flake8"
FORWARDERS = (
    "example",
    "nostr",
    "rabbitmq",
    "webhook",
)
SELECTED = "select = E9,E722,F63,F7,F82"


def run_flake8(*args):
    return subprocess.run(
        [sys.executable, "-m", "flake8", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_config_and_logger_bindings_have_no_f821_suppression():
    """The gate file selects the right codes, and the loader-injected
    logger bindings in the built-in forwarders carry no F821 suppression."""
    assert CONFIG.is_file(), f"gate config missing: {CONFIG}"
    config_text = CONFIG.read_text()
    assert SELECTED in config_text
    assert "ignore" not in config_text

    for name in FORWARDERS:
        path = ROOT / "src" / "notificationforwarder" / name / "forwarder.py"
        text = path.read_text()
        assert "logger = None" in text, f"{name}: loader binding missing"
        assert "noqa: F821" not in text, f"{name}: F821 suppression present"


def test_gate_flags_undefined_name_but_not_bound_logger(tmp_path):
    """A module that binds ``logger = None`` and also uses an undefined name:
    the gate must flag the undefined name with F821 and leave the bound
    logger alone, proving the bindings do not hide other F821 findings."""
    probe = tmp_path / "probe.py"
    probe.write_text(
        "logger = None\n"
        "\n"
        "\n"
        "def use_logger():\n"
        "    logger.info('bound')\n"
        "    return gate_probe_undefined_name\n",
    )
    result = run_flake8("--config", str(CONFIG), str(probe))
    assert result.returncode != 0, result.stdout + result.stderr
    f821_lines = [line for line in result.stdout.splitlines() if "F821" in line]
    # flake8 quotes the flagged name; match it quoted so file paths in the
    # output (e.g. a tmp dir named after the test) cannot fake a match.
    assert any("'gate_probe_undefined_name'" in line for line in f821_lines)
    assert not any("'logger'" in line for line in f821_lines)


def test_missing_config_fails_closed(tmp_path):
    """An explicit nonexistent config must fail closed, not default to
    built-ins and pass."""
    target = tmp_path / "trivial.py"
    target.write_text("x = 1\n")
    result = run_flake8("--config", str(tmp_path / "does_not_exist.cfg"), str(target))
    assert result.returncode != 0
