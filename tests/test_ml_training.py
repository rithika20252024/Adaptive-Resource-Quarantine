import json
import tempfile
import unittest
from pathlib import Path

from arq.core.ml_training import (
    load_isolation_forest,
    load_jsonl,
    train_isolation_forest,
)


def write_dataset(path, count=100):
    with path.open("w", encoding="utf-8") as stream:
        for i in range(count):
            row = {
                "cpu_percent": 5 + (i % 20),
                "memory_rss_mb": 100 + i * 2,
                "memory_vms_mb": 300 + i * 3,
                "memory_growth_mb_s": (i % 5) * 0.2,
                "io_read_kb_s": 10 + i,
                "io_write_kb_s": 15 + (i % 10),
                "num_threads": 1 + (i % 8),
            }
            stream.write(json.dumps(row) + "\n")


class TestMLTraining(unittest.TestCase):
    def test_training_and_model_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "normal.jsonl"
            write_dataset(dataset)

            result = train_isolation_forest(
                dataset, output_dir=root / "models"
            )

            self.assertEqual(result["training_rows"], 75)
            self.assertEqual(result["calibration_rows"], 25)
            artifact = load_isolation_forest(result["model_path"])
            self.assertEqual(artifact["feature_names"], [
                "cpu_percent",
                "memory_rss_mb",
                "memory_vms_mb",
                "memory_growth_mb_s",
                "io_read_kb_s",
                "io_write_kb_s",
                "num_threads",
            ])

    def test_too_few_records_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "small.jsonl"
            write_dataset(dataset, count=10)
            with self.assertRaises(ValueError):
                load_jsonl(dataset)

    def test_invalid_record_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "bad.jsonl"
            dataset.write_text('{"cpu_percent": "bad"}\n')
            with self.assertRaises(ValueError):
                load_jsonl(dataset)

    def test_contamination_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "normal.jsonl"
            write_dataset(dataset)
            with self.assertRaises(ValueError):
                train_isolation_forest(dataset, contamination=0.8)


if __name__ == "__main__":
    unittest.main()
