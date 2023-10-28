import pytest
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = "true"


def test_import():
    import notificationforwarder.baseclass
    assert hasattr(notificationforwarder, "baseclass")
    assert hasattr(notificationforwarder.baseclass, "new")

