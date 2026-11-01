"""Checks that benign look-alikes really resemble attacks, and don't disturb normal traffic."""

import collections
import datetime
import statistics
import unittest

import generate
from zsgen.traffic import simulate_browsing
from zsgen.world import build_world, headcount_by_department

SEED, USERS = 7, 10


def _key(req):
    return (req.ts, req.user.login, req.host, req.path, req.status, req.reqsize, req.respsize)


class LookalikeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = generate.build_requests(seed=SEED, users=USERS, days=1)
        cls.by_label = collections.defaultdict(list)
        for req in cls.requests:
            cls.by_label[req.label].append(req)

    def test_normal_browsing_is_unchanged_by_lookalikes(self):
        # Separate random streams: adding look-alikes must not alter ordinary traffic at all.
        world = build_world(generate.rng_for(SEED, "world"), USERS)
        start = datetime.datetime.combine(generate.DEFAULT_START, datetime.time(), datetime.UTC)
        alone = simulate_browsing(world, generate.rng_for(SEED, "browsing"), start.timestamp(), 1)
        self.assertEqual(sorted(map(_key, alone)), sorted(map(_key, self.by_label[None])))

    def test_heartbeats_look_like_beaconing(self):
        beats = self.by_label["benign:security_agent_heartbeat"]
        self.assertEqual({r.user.login for r in beats}, {r.user.login for r in self.requests})
        one_device = sorted(r.ts for r in beats if r.user == beats[0].user)
        gaps = [b - a for a, b in zip(one_device, one_device[1:], strict=False)]
        self.assertAlmostEqual(statistics.mean(gaps), 1800, delta=60)  # every ~30 minutes
        self.assertLess(statistics.stdev(gaps) / statistics.mean(gaps), 0.05)  # very regular
        self.assertLessEqual(max(r.reqsize for r in beats) - min(r.reqsize for r in beats), 40)
        self.assertTrue(any(r.ts % 86400 < 4 * 3600 for r in beats))  # also at night

    def test_update_checks_are_hourly_on_every_device(self):
        checks = self.by_label["benign:update_check"]
        per_device = collections.Counter(r.user.login for r in checks)
        self.assertEqual(len(per_device), USERS)
        self.assertTrue(all(23 <= n <= 25 for n in per_device.values()))

    def test_it_automation_looks_like_a_bot_but_succeeds(self):
        calls = self.by_label["benign:it_automation"]
        self.assertTrue(calls)
        self.assertEqual({r.user.dept for r in calls}, {"IT"})
        self.assertTrue(all(r.status == 200 for r in calls))
        agents = {r.useragent.split("/")[0] for r in calls}
        self.assertEqual(agents, {"python-requests", "curl"})
        self.assertTrue(any(2 * 3600 <= r.ts % 86400 < 3 * 3600 for r in calls))  # overnight

    def test_large_upload_is_upload_heavy_to_the_company_drive(self):
        chunks = self.by_label["benign:large_upload"]
        self.assertGreater(sum(r.reqsize for r in chunks), 150_000_000)
        self.assertTrue(all(r.respsize < 1_000 for r in chunks))
        self.assertEqual({r.host for r in chunks}, {"files.officesuite.example"})
        self.assertEqual({r.user.dept for r in chunks}, {"Sales"})
        self.assertTrue(all(15 * 3600 <= r.ts % 86400 < 17 * 3600 for r in chunks))

    def test_labels_never_reach_the_log(self):
        lines = generate.generate(seed=SEED, users=USERS, days=1)
        self.assertEqual(len(lines), len(self.requests))
        self.assertFalse(any("benign:" in line or "attack:" in line for line in lines))


class HeadcountTest(unittest.TestCase):
    def test_every_department_is_staffed_and_totals_match(self):
        for n in range(5, 60):
            counts = headcount_by_department(n)
            self.assertEqual(sum(counts.values()), n)
            self.assertTrue(all(c >= 1 for c in counts.values()), (n, counts))

    def test_too_few_users_is_an_error(self):
        with self.assertRaises(ValueError):
            headcount_by_department(4)


if __name__ == "__main__":
    unittest.main()
