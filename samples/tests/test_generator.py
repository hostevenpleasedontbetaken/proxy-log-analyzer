"""Checks that generated logs are reproducible, match the real Zscaler format, and stay safe.

Run: python -m unittest discover -s samples/tests -t samples
"""

import base64
import calendar
import collections
import gzip
import ipaddress
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import generate
from zsgen.world import COMPANY_DOMAIN, DOCUMENTATION_NETWORKS
from zsgen.zscaler import FIELDS

SAMPLES_DIR = Path(__file__).resolve().parents[1]


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = generate.generate(seed=7, users=10, days=1)
        cls.events = [json.loads(line)["event"] for line in cls.lines]

    def test_same_seed_gives_identical_output(self):
        self.assertEqual(generate.generate(seed=7, users=10, days=1), self.lines)

    def test_different_seed_gives_different_output(self):
        self.assertNotEqual(generate.generate(seed=8, users=10, days=1), self.lines)

    def test_output_does_not_depend_on_python_hash_seed(self):
        # Python randomizes string hashing per process; iterating a set would change the order.
        outputs = []
        for hash_seed in ("1", "2"):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "out.ndjson"
                subprocess.run(
                    [sys.executable, "generate.py", "--out", str(out), "--users", "5"],
                    cwd=SAMPLES_DIR,
                    env={**os.environ, "PYTHONHASHSEED": hash_seed},
                    check=True,
                    capture_output=True,
                )
                outputs.append(out.read_bytes())
        self.assertEqual(outputs[0], outputs[1])

    def test_gzip_output_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "a.ndjson.gz", Path(tmp) / "b.ndjson.gz"
            generate.write(self.lines, first)
            generate.write(self.lines, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(gzip.decompress(first.read_bytes()).decode().splitlines(), self.lines)

    def test_lines_use_the_v12_envelope_with_string_values(self):
        for line in self.lines:
            envelope = json.loads(line)
            self.assertEqual(envelope["version"], "v12")
            self.assertEqual(envelope["sourcetype"], "zscalernss-web")
            self.assertEqual(list(envelope["event"]), FIELDS)
            self.assertTrue(all(isinstance(v, str) for v in envelope["event"].values()))

    def test_b64url_decodes_to_host_and_path(self):
        for event in self.events:
            url = base64.b64decode(event["b64url"]).decode()
            self.assertTrue(url.startswith(event["host"] + "/"), url)

    def test_time_and_epochtime_agree(self):
        for event in self.events:
            parsed = time.strptime(event["time"], "%a %b %d %H:%M:%S %Y")
            self.assertEqual(int(event["epochtime"]), calendar.timegm(parsed))

    def test_record_ids_are_unique_and_in_time_order(self):
        ids = [int(e["recordid"]) for e in self.events]
        self.assertEqual(ids, sorted(set(ids)))
        epochs = [int(e["epochtime"]) for e in self.events]
        self.assertEqual(epochs, sorted(epochs))

    def test_only_fictional_hosts_users_and_documentation_ips(self):
        for event in self.events:
            self.assertTrue(event["host"].endswith(".example"), event["host"])
            self.assertTrue(event["login"].endswith("@" + COMPANY_DOMAIN))
            if event["serverip"] != "None":  # None = the domain never resolved
                ip = ipaddress.ip_address(event["serverip"])
                self.assertTrue(any(ip in net for net in DOCUMENTATION_NETWORKS), ip)
            self.assertTrue(ipaddress.ip_address(event["cltip"]).is_private)

    def test_browsing_follows_the_working_day(self):
        # Ordinary traffic only: software and malware intentionally run all night.
        requests = generate.build_requests(seed=7, users=10, days=1)
        hours = collections.Counter(int(r.ts % 86400 // 3600) for r in requests if not r.label)
        working = sum(hours[h] for h in range(10, 16))
        night = sum(hours[h] for h in range(0, 6))
        self.assertGreater(working, 20 * max(night, 1))

    def test_policy_blocks_follow_the_rules(self):
        blocked = [e for e in self.events if e["action"] == "Blocked"]
        self.assertTrue(blocked)
        self.assertTrue(all(e["respcode"] == "403" for e in blocked))
        for event in blocked:
            if event["rulelabel"] == "Block_Social_Finance_HR":
                self.assertEqual(event["urlsubcat"], "Social Networking")
                self.assertIn(event["dept"], {"Finance", "HR"})
            if event["rulelabel"] == "Block_Streaming":
                self.assertEqual(event["urlsubcat"], "Streaming Media")


if __name__ == "__main__":
    unittest.main()
