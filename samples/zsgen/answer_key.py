"""The answer key (`*.ground_truth.json`): which log lines are planted attacks, and which are
benign look-alikes, identified by `recordid`. The evaluation in M5 compares detections to it.

    {
      "generator": {"seed": 42, "users": 30, "days": 1, "start": "2026-10-20", ...},
      "attacks": [
        {"name": "phishing", "description": "...", "users": ["..."], "first_seen": "...",
         "last_seen": "...", "line_count": 4, "recordids": ["7000000000000004113", ...]},
        ...
      ],
      "benign_lookalikes": [ ...same shape... ]
    }
"""

import datetime

from zsgen.lookalikes import DESCRIPTIONS as LOOKALIKE_DESCRIPTIONS
from zsgen.request import Request
from zsgen.scenarios import SCENARIOS


def _iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(int(ts), datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(requests: list[Request], first_record_id: int, generator: dict) -> dict:
    """`requests` must be in log order: request i got record id `first_record_id + i`."""
    groups: dict[str, list[tuple[int, Request]]] = {}
    for i, req in enumerate(requests):
        if req.label:
            groups.setdefault(req.label, []).append((first_record_id + i, req))

    key: dict = {"generator": generator, "attacks": [], "benign_lookalikes": []}
    for label, members in groups.items():
        kind, name = label.split(":", 1)
        if kind == "attack":
            description, section = SCENARIOS[name].description, "attacks"
        else:
            description, section = LOOKALIKE_DESCRIPTIONS[name], "benign_lookalikes"
        key[section].append(
            {
                "name": name,
                "description": description,
                "users": sorted({req.user.login for _, req in members}),
                "first_seen": _iso(members[0][1].ts),
                "last_seen": _iso(members[-1][1].ts),
                "line_count": len(members),
                # Strings, like `recordid` in the log itself.
                "recordids": [str(record_id) for record_id, _ in members],
            }
        )
    for section in ("attacks", "benign_lookalikes"):
        key[section].sort(key=lambda entry: (entry["first_seen"], entry["name"]))
    return key
