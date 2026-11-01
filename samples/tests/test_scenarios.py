"""Checks each planted attack has its defining traits, and that the answer key points at
exactly the right log lines."""

import json
import tempfile
import unittest
from pathlib import Path

import generate

SEED, USERS = 7, 10


def _key(req):
    return (req.ts, req.user.login, req.host, req.path, req.status, req.reqsize, req.respsize)


class ScenarioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = generate.build_requests(seed=SEED, users=USERS, days=1)
        cls.attack = {
            name: [r for r in cls.requests if r.label == f"attack:{name}"]
            for name in generate.ALL_ATTACKS
        }

    def test_every_attack_is_planted(self):
        for name, requests in self.attack.items():
            self.assertTrue(requests, name)

    def test_malware_download_is_blocked_with_threat_details(self):
        downloads = [r for r in self.attack["malware_download"] if r.filename]
        self.assertEqual(len(downloads), 2)  # the user tried twice
        for r in downloads:
            self.assertEqual((r.action, r.status), ("Blocked", 403))
            self.assertTrue(r.filename.endswith(".exe"))
            self.assertEqual(r.threatseverity, "Critical (90–100)")
            self.assertGreaterEqual(r.riskscore, 90)
        self.assertEqual(self.attack["malware_download"][0].category[1], "Miscellaneous or Unknown")

    def test_phishing_page_is_visited_then_the_form_is_posted(self):
        requests = sorted(self.attack["phishing"], key=lambda r: r.ts)
        self.assertEqual(requests[0].referer, "mail.officesuite.example")  # came from an email
        self.assertEqual(requests[-1].method, "POST")
        self.assertTrue(all(r.category[1] == "Phishing" for r in requests))
        self.assertEqual(len({r.user.login for r in requests}), 1)

    def test_policy_probing_is_many_blocked_anonymizer_attempts(self):
        tries = self.attack["policy_probing"]
        self.assertGreaterEqual(len(tries), 15)
        self.assertTrue(all(r.action == "Blocked" and r.category[1] == "Anonymizer" for r in tries))
        self.assertGreaterEqual(len({r.host for r in tries}), 2)
        self.assertLess(max(r.ts for r in tries) - min(r.ts for r in tries), 30 * 60)

    def test_exfiltration_is_large_late_uploads_of_sensitive_files(self):
        uploads = [r for r in self.attack["data_exfiltration"] if r.method == "POST"]
        self.assertGreater(sum(r.reqsize for r in uploads), 50_000_000)
        self.assertTrue(all(r.reqsize > 1_000 * r.respsize for r in uploads))
        self.assertTrue(all(r.upload_filename for r in uploads))
        self.assertTrue(all(r.ts % 86400 >= 23 * 3600 for r in uploads))
        self.assertEqual({r.user.dept for r in uploads}, {"Finance"})

    def test_scanning_is_a_fast_burst_of_mostly_404s_from_a_script(self):
        scan = self.attack["scanning"]
        self.assertGreaterEqual(len(scan), 500)
        self.assertLess(max(r.ts for r in scan) - min(r.ts for r in scan), 180)
        self.assertGreater(sum(r.status == 404 for r in scan) / len(scan), 0.7)
        self.assertEqual({r.useragent for r in scan}, {"python-requests/2.31.0"})
        self.assertEqual(len({r.user.device for r in scan}), 1)

    def test_generated_domains_are_many_random_names_that_mostly_fail(self):
        lookups = self.attack["generated_domains"]
        self.assertGreaterEqual(len({r.host for r in lookups}), 50)
        self.assertLess(max(r.ts for r in lookups) - min(r.ts for r in lookups), 5 * 60)
        self.assertGreater(sum(r.status != 200 for r in lookups) / len(lookups), 0.8)
        self.assertTrue(all(r.serverip is None for r in lookups if r.status != 200))

    def test_c2_beacons_every_minute_all_day_from_the_infected_laptop(self):
        beacons = sorted(self.attack["c2_beaconing"], key=lambda r: r.ts)
        gaps = [b.ts - a.ts for a, b in zip(beacons, beacons[1:], strict=False)]
        self.assertAlmostEqual(sum(gaps) / len(gaps), 60, delta=2)
        self.assertLess(max(gaps), 66)
        self.assertGreater(beacons[-1].ts - beacons[0].ts, 18 * 3600)
        self.assertEqual(len({r.host for r in beacons}), 1)
        self.assertLessEqual(
            max(r.respsize for r in beacons) - min(r.respsize for r in beacons), 16
        )
        # Same device that searched for the command server, and it found this host.
        dga = self.attack["generated_domains"]
        self.assertEqual({r.user.device for r in beacons}, {r.user.device for r in dga})
        self.assertIn(beacons[0].host, {r.host for r in dga if r.status == 200})

    def test_compromised_account_is_a_known_login_on_an_unknown_device_at_night(self):
        session = self.attack["compromised_account"]
        login = session[0].user.login
        usual_devices = {
            r.user.device for r in self.requests if r.user.login == login and not r.label
        }
        self.assertTrue(usual_devices)
        self.assertTrue(all(r.user.device not in usual_devices for r in session))
        self.assertTrue(all(3 * 3600 <= r.ts % 86400 < 5 * 3600 for r in session))
        exports = [r for r in session if "/export" in r.path]
        self.assertGreater(sum(r.respsize for r in exports), 50_000_000)

    def test_attacks_do_not_change_other_traffic(self):
        clean = generate.build_requests(seed=SEED, users=USERS, days=1, attacks=())
        not_attacks = [r for r in self.requests if not (r.label or "").startswith("attack:")]
        self.assertEqual(list(map(_key, clean)), list(map(_key, not_attacks)))

    def test_a_subset_of_attacks_is_identical_to_the_same_attacks_in_a_full_run(self):
        only = generate.build_requests(seed=SEED, users=USERS, days=1, attacks=("phishing",))
        phishing = [r for r in only if r.label == "attack:phishing"]
        self.assertEqual(list(map(_key, phishing)), list(map(_key, self.attack["phishing"])))
        self.assertFalse(any((r.label or "").startswith("attack:malware") for r in only))


class AnswerKeyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        log = Path(tmp.name) / "acme.ndjson.gz"
        generate.main(["--out", str(log), "--seed", str(SEED), "--users", str(USERS)])
        cls.key_path = Path(tmp.name) / "acme.ground_truth.json"
        cls.key = json.loads(cls.key_path.read_text())
        cls.events = {
            e["recordid"]: e
            for e in (
                json.loads(line)["event"] for line in generate.generate(seed=SEED, users=USERS)
            )
        }

    def test_key_is_written_next_to_the_log(self):
        self.assertTrue(self.key_path.exists())
        self.assertEqual(self.key["generator"]["seed"], SEED)

    def test_every_attack_has_an_entry(self):
        self.assertEqual({a["name"] for a in self.key["attacks"]}, set(generate.ALL_ATTACKS))

    def test_record_ids_point_at_the_right_lines(self):
        for entry in self.key["attacks"] + self.key["benign_lookalikes"]:
            self.assertEqual(len(entry["recordids"]), entry["line_count"])
            for record_id in entry["recordids"]:
                self.assertIn(self.events[record_id]["login"], entry["users"])
        exfil = next(a for a in self.key["attacks"] if a["name"] == "data_exfiltration")
        hosts = {self.events[rid]["host"] for rid in exfil["recordids"]}
        self.assertEqual(hosts, {"www.dropbin.example"})

    def test_no_line_is_in_two_groups(self):
        ids = [
            rid
            for e in self.key["attacks"] + self.key["benign_lookalikes"]
            for rid in e["recordids"]
        ]
        self.assertEqual(len(ids), len(set(ids)))

    def test_clean_run_has_no_attacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "clean.ndjson"
            generate.main(["--out", str(log), "--users", "5", "--attacks", "none"])
            key = json.loads((Path(tmp) / "clean.ground_truth.json").read_text())
            self.assertEqual(key["attacks"], [])
            self.assertTrue(key["benign_lookalikes"])

    def test_unknown_attack_name_is_rejected(self):
        with self.assertRaises(SystemExit), tempfile.TemporaryDirectory() as tmp:
            generate.main(["--out", str(Path(tmp) / "x.ndjson"), "--attacks", "nope"])


if __name__ == "__main__":
    unittest.main()
