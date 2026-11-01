"""The committed sample files must be exactly what build_samples.py produces, so the README and
the detection results always describe the files people actually upload."""

import json
import tempfile
import unittest
from pathlib import Path

import build_samples


class CommittedSamplesTest(unittest.TestCase):
    def test_committed_files_match_a_fresh_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            for fresh in build_samples.build(Path(tmp)):
                committed = build_samples.SAMPLES_DIR / fresh.name
                self.assertTrue(committed.exists(), f"{fresh.name} is missing; run make samples")
                self.assertEqual(
                    committed.read_bytes(),
                    fresh.read_bytes(),
                    f"{fresh.name} is out of date; run make samples",
                )

    def test_wrong_format_sample_is_not_zscaler(self):
        lines = (build_samples.SAMPLES_DIR / "not-zscaler.log").read_text().splitlines()
        self.assertTrue(lines)
        for line in lines:
            with self.assertRaises(json.JSONDecodeError):
                json.loads(line)


if __name__ == "__main__":
    unittest.main()
