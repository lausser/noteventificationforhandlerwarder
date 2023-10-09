from unittest import TestCase

class NofEvhTest(TestCase):
    def test_import(self):
        import notificationforwarder
        self.assertTrue(hasattr(notificationforwarder, "new"))

