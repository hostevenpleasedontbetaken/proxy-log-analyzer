"""Generate realistic Zscaler NSS web logs (one JSON object per line, Elastic v12 template),
with planted attacks and an answer key saying which lines they are.

    python samples/generate.py --out /tmp/acme.ndjson --users 30 --days 1 --seed 42
    → /tmp/acme.ndjson               the log
    → /tmp/acme.ground_truth.json    the answer key

Same arguments → byte-identical files, so tests and the committed samples are reproducible.
A `.gz` output path writes a gzip file. `--attacks none` gives a clean file.

The generator is deliberately independent of the backend: if both shared one field mapping,
a mapping bug would match on both sides and never show up in tests.
"""

import argparse
import datetime
import gzip
import json
import random
import sys
from pathlib import Path

from zsgen import answer_key, zscaler
from zsgen.lookalikes import simulate_lookalikes
from zsgen.request import Request
from zsgen.scenarios import SCENARIOS
from zsgen.traffic import simulate_browsing
from zsgen.world import build_world

DEFAULT_START = datetime.date(2026, 10, 20)  # a Tuesday
FIRST_RECORD_ID = 7_000_000_000_000_000_000  # Zscaler record ids are large 64-bit numbers
ALL_ATTACKS = tuple(SCENARIOS)


def rng_for(seed: int, part: str) -> random.Random:
    """A separate random stream per part of the simulation, so adding or removing a part
    (e.g. one attack scenario) doesn't change what the other parts generate."""
    return random.Random(f"{seed}:{part}")


def build_requests(
    *,
    seed: int = 42,
    users: int = 30,
    days: int = 1,
    start: datetime.date = DEFAULT_START,
    attacks: tuple[str, ...] = ALL_ATTACKS,
) -> list[Request]:
    """Every simulated request, in log order, still carrying its answer-key label."""
    world = build_world(rng_for(seed, "world"), users)
    start_ts = int(datetime.datetime.combine(start, datetime.time(), datetime.UTC).timestamp())

    requests = [
        *simulate_browsing(world, rng_for(seed, "browsing"), start_ts, days),
        *simulate_lookalikes(world, rng_for(seed, "lookalikes"), start_ts, days),
    ]
    for name in attacks:
        requests += SCENARIOS[name].plant(rng_for(seed, f"attack:{name}"), world, start_ts)
    requests.sort(key=lambda r: (r.ts, r.user.login, r.host, r.path))
    return requests


def to_lines(requests: list[Request]) -> list[str]:
    """Serialize in order; request i gets record id FIRST_RECORD_ID + i."""
    return [
        zscaler.to_line(zscaler.to_event(req, FIRST_RECORD_ID + i))
        for i, req in enumerate(requests)
    ]


def generate(**options) -> list[str]:
    """The log file's lines. Takes the same keyword options as `build_requests`."""
    return to_lines(build_requests(**options))


def answer_key_path(log_path: Path) -> Path:
    """acme.ndjson.gz → acme.ground_truth.json (next to the log)."""
    stem = log_path.name.removesuffix(".gz").removesuffix(".ndjson")
    return log_path.with_name(f"{stem}.ground_truth.json")


def write(lines: list[str], path: Path) -> None:
    data = ("\n".join(lines) + "\n").encode()
    if path.suffix == ".gz":
        # mtime=0 and no filename keep the gzip header identical between runs.
        with open(path, "wb") as raw, gzip.GzipFile("", "wb", fileobj=raw, mtime=0) as gz:
            gz.write(data)
    else:
        path.write_bytes(data)


def parse_attacks(value: str) -> tuple[str, ...]:
    if value == "all":
        return ALL_ATTACKS
    if value == "none":
        return ()
    names = tuple(value.split(","))
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown attack(s) {', '.join(unknown)}; choose from {', '.join(SCENARIOS)}"
        )
    return names


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help=".ndjson or .ndjson.gz")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--users", type=int, default=30)
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument(
        "--start",
        type=datetime.date.fromisoformat,
        default=DEFAULT_START,
        help="first day, YYYY-MM-DD (UTC)",
    )
    parser.add_argument(
        "--attacks",
        type=parse_attacks,
        default=ALL_ATTACKS,
        help="'all' (default), 'none', or a comma-separated list of: " + ", ".join(SCENARIOS),
    )
    args = parser.parse_args(argv)

    options = {"seed": args.seed, "users": args.users, "days": args.days, "start": args.start}
    requests = build_requests(**options, attacks=args.attacks)
    write(to_lines(requests), args.out)

    generator = {**options, "start": args.start.isoformat(), "attacks": list(args.attacks)}
    key = answer_key.build(requests, FIRST_RECORD_ID, generator)
    key_path = answer_key_path(args.out)
    key_path.write_text(json.dumps(key, indent=2) + "\n")

    size_mb = args.out.stat().st_size / 1_000_000
    print(f"wrote {len(requests):,} lines ({size_mb:.1f} MB) to {args.out}", file=sys.stderr)
    print(f"wrote answer key ({len(key['attacks'])} attacks) to {key_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
