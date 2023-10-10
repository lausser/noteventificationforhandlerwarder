import pytest

def test_import():
    import notificationforwarder
    assert hasattr(notificationforwarder, "baseclass")
    assert hasattr(notificationforwarder.baseclass, "new")

