from unittest import TestCase
import os
import shutil
import notificationforwarder
import logging

class NofEvhTest(TestCase):


    def setUp(self):
        omd_root = os.path.dirname(__file__)
        os.environ["OMD_ROOT"] = omd_root
        shutil.rmtree(omd_root+"/var", ignore_errors=True)
        os.makedirs(omd_root+"/var/log", 0o755)
        shutil.rmtree(omd_root+"/var", ignore_errors=True)
        os.makedirs(omd_root+"/var/tmp", 0o755)
        shutil.rmtree(omd_root+"/tmp", ignore_errors=True)
        os.makedirs(omd_root+"/tmp", 0o755)


    def get_logfile(self, forwarder):
        logger_name = "notificationforwarder_"+forwarder.name
        logger = logging.getLogger(logger_name)
        return [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]


    def test_dummy_forwarder(self):
        reveiveropts = {
            "username": "dau",
            "password": "i_bims_1_dau",
        }
        example = notificationforwarder.new("example", None, True, True,  reveiveropts)
        self.assertEqual(example.__class__.__name__, "Example")
        self.assertEqual(example.password, "i_bims_1_dau")
        self.assertEqual(example.queued_events, [])


    def _test_dummy_formatter(self):
        example = notificationforwarder.new("example", None, True, True,  {})
        fexample = example.formatter()
        self.assertEqual(fexample.__class__.__name__, "ExampleFormatter")


    def test_dummy_logging(self):
        example = notificationforwarder.new("example", None, True, True,  {})
        logger_name = "notificationforwarder_"+example.name
        logger = logging.getLogger(logger_name)
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "notificationforwarder_example")
        self.assertEqual(len(logger.handlers), 2)
        logfile = [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]
        self.assertTrue(logfile.endswith("notificationforwarder_example.log"))

        example = notificationforwarder.new("example", "2", True, True,  {})
        logger_name = "notificationforwarder_2_"+example.name
        logger = logging.getLogger(logger_name)
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "notificationforwarder_2_example")
        self.assertEqual(len(logger.handlers), 2)
        logfile = [h.baseFilename for h in logger.handlers if hasattr(h, "baseFilename")][0]
        self.assertTrue(logfile.endswith("notificationforwarder_2_example.log"))
        

    def _test_dummy_formatter_format_event(self):
        example = notificationforwarder.new("example", None, True, True,  {})
        fexample = example.formatter()
        raw_event = {
            "description": "this is an example description",
        }
        event = fexample.format_event(raw_event)
        self.assertEqual(event.summary, "this is an example")
        self.assertEqual(event.payload["description"], "this is an example description")
        self.assertAlmostEqual(event.payload["timestamp"], None, None, 10)


    def test_dummy_forwarder_forward(self):
        reveiveropts = {
            "username": "dau",
            "password": "i_bims_1_dau",
        }
        eventopts = {
            "description": "this is an example description",
        }
        example = notificationforwarder.new("example", None, True, True,  reveiveropts)
        example.forward(eventopts)
        log = open(self.get_logfile(example)).read()
        self.assertTrue("INFO - dau submits" in log)
        self.assertTrue("'description': 'this is an example description'" in log)
        # this is the global log, written by the baseclass
        self.assertTrue("INFO - forwarded this is an example" in log)

        self.setUp() # delete logfile
        # we need to reinitialize, because the logger has the (deleted) file
        # still open and further writes would end up in nirvana.
        example = notificationforwarder.new("example", None, True, True,  reveiveropts)
        eventopts = {
            "description": "this is an example description again",
        }
        example.no_more_logging()
        example.forward(eventopts)
        log = open(self.get_logfile(example)).read()
        # the formatter's logs are still there
        self.assertTrue("INFO - dau submits" in log)
        self.assertTrue("'description': 'this is an example description again'" in log)
        # but not the baseclasse's log
        self.assertFalse("INFO - forwarded this is an example" in log)


