"""Generate realistic Zscaler NSS web logs (one JSON object per line, Elastic v12 template).

    python samples/generate.py --out /tmp/acme.ndjson --users 30 --days 1 --seed 42

Same arguments → byte-identical file, so tests and the committed samples are reproducible.
A `.gz` output path writes a gzip file.

The generator is deliberately independent of the backend: if both shared one field mapping,
a mapping bug would match on both sides and never show up in tests.
"""

import argparse
import datetime
import gzip
import random
import sys
from pathlib import Path

from zsgen import zscaler
from zsgen.lookalikes import simulate_lookalikes
from zsgen.request import Request
from zsgen.traffic import simulate_browsing
from zsgen.world import build_world

DEFAULT_START = datetime.date(2026, 10, 20)  # a Tuesday
FIRST_RECORD_ID = 7_000_000_000_000_000_000  # Zscaler record ids are large 64-bit numbers


def rng_for(seed: int, part: str) -> random.Random:
    """A separate random stream per part of the simulation, so adding a part later
    (e.g. attack scenarios) doesn't change what the other parts generate."""
    return random.Random(f"{seed}:{part}")


def build_requests(
    *, seed: int = 42, users: int = 30, days: int = 1, start: datetime.date = DEFAULT_START
) -> list[Request]:
    """Every simulated request, in time order, still carrying its answer-key label."""
    world = build_world(rng_for(seed, "world"), users)
    start_ts = int(datetime.datetime.combine(start, datetime.time(), datetime.UTC).timestamp())

    requests = [
        *simulate_browsing(world, rng_for(seed, "browsing"), start_ts, days),
        *simulate_lookalikes(world, rng_for(seed, "lookalikes"), start_ts, days),
    ]
    requests.sort(key=lambda r: (r.ts, r.user.login, r.host, r.path))
    return requests


def generate(
    *, seed: int = 42, users: int = 30, days: int = 1, start: datetime.date = DEFAULT_START
) -> list[str]:
    """The log file's lines: each request serialized, with record ids in time order."""
    requests = build_requests(seed=seed, users=users, days=days, start=start)
    return [
        zscaler.to_line(zscaler.to_event(req, FIRST_RECORD_ID + i))
        for i, req in enumerate(requests)
    ]


def write(lines: list[str], path: Path) -> None:
    data = ("\n".join(lines) + "\n").encode()
    if path.suffix == ".gz":
        # mtime=0 and no filename keep the gzip header identical between runs.
        with open(path, "wb") as raw, gzip.GzipFile("", "wb", fileobj=raw, mtime=0) as gz:
            gz.write(data)
    else:
        path.write_bytes(data)


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
    args = parser.parse_args(argv)

    lines = generate(seed=args.seed, users=args.users, days=args.days, start=args.start)
    write(lines, args.out)
    size_mb = args.out.stat().st_size / 1_000_000
    print(f"wrote {len(lines):,} lines ({size_mb:.1f} MB) to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
