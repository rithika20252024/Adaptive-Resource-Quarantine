import os
import unittest
from arq.core.monitor import ProcessMonitor

class TestProcessMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = ProcessMonitor()

    def test_sample_self(self):
        pid = os.getpid()
        m = self.monitor.sample_process(pid)
        self.assertIsNotNone(m)
        self.assertEqual(m.pid, pid)
        self.assertGreaterEqual(m.cpu_percent, 0.0)
        self.assertGreater(m.memory_rss_mb, 0.0)

    def test_sample_invalid_pid(self):
        m = self.monitor.sample_process(999999)
        self.assertIsNone(m)

    def test_sample_all(self):
        pid = os.getpid()
        results = self.monitor.sample_all([pid])
        self.assertEqual(len(results), 1)

    def test_cpu_delta_second_sample(self):
        import time
        pid = os.getpid()
        self.monitor.sample_process(pid)
        time.sleep(0.1)
        m = self.monitor.sample_process(pid)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(m.cpu_percent, 0.0)

if __name__ == "__main__":
    unittest.main()
