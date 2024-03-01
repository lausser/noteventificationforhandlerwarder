import pytest
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = "true"


def test_import():
    import eventhandler.baseclass
    assert hasattr(eventhandler, "baseclass")
    assert hasattr(eventhandler.baseclass, "new")

