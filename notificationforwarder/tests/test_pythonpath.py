from unittest import TestCase

class NofEvhTest(TestCase):
    def test_import(self):
        from notificationforwarder import new
        self.assertTrue(hasattr(notificationforwarder, "new"))

