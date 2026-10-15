"""
Unit tests for Process Telemetry Monitor.
"""

import os
import unittest
from arq.core.monitor import ProcessMonitor

class TestProcessMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = ProcessMonitor()
        self.self_pid = os.getpid()

    def test_sample_self_process(self):
        metrics = self.monitor.sample_process(self.self_pid)
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.pid, self.self_pid)
        self.assertGreater(metrics.memory_rss_mb, 0.0)
        self.assertGreaterEqual(metrics.num_threads, 1)

    def test_sample_nonexistent_process(self):
        metrics = self.monitor.sample_process(99999999)
        self.assertIsNone(metrics)

if __name__ == "__main__":
    unittest.main()
