"""Measure detection against the samples' answer keys and write the results as Markdown.

    python -m app.evaluation > ../docs/RESULTS.md     (or: make evaluate)

For each sample file: run the same parse → detect pipeline an upload uses, then check every
planted attack (was it in a High incident? how confident? which detectors?), every benign
look-alike (did any of its lines reach High?) and every High incident (was it real?).
The output is deterministic (Isolation Forest uses a fixed seed), so the committed
docs/RESULTS.md can be checked against a fresh run in the tests.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from app.detection import Detection, detect
from app.detection.findings import band
from app.parsing import parse_upload
from app.stats import to_frame

SAMPLES = Path(__file__).resolve().parents[2] / "samples"  # /samples in docker compose
SAMPLE_FILES = ["acme-web-day.ndjson.gz", "acme-web-small.ndjson", "acme-web-clean.ndjson"]
SEVERITY = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}


@dataclass
class AttackResult:
    name: str
    lines: int
    flagged_lines: int  # attack lines covered by any finding
    confidence: float  # best incident that includes the attack's lines
    severity: int
    detectors: list[str]

    @property
    def caught(self) -> bool:
        return band(self.confidence) == "High"


@dataclass
class LookalikeResult:
    name: str
    lines: int
    highest_confidence: float  # highest score on any of its lines (0 = never flagged)
    detectors: list[str]


@dataclass
class FileResult:
    name: str
    lines: int
    attacks: list[AttackResult]
    lookalikes: list[LookalikeResult]
    high_incidents: int
    high_incidents_with_attack: int
    ml_ran: bool
    ml_top_hours: list[tuple[str, str, str]]  # (user, hour, what it really was)

    @property
    def ml_attacks(self) -> int:
        return sum(truth.startswith("attack: ") for _, _, truth in self.ml_top_hours)


def evaluate_file(name: str) -> FileResult:
    rows = parse_upload((SAMPLES / name).read_bytes()).rows
    detection = detect(to_frame(rows))
    stem = name.removesuffix(".gz").removesuffix(".ndjson")
    key = json.loads((SAMPLES / f"{stem}.ground_truth.json").read_text())
    line_of = {row["record_id"]: row["line_no"] for row in rows}

    def lines_of(entry: dict) -> set[int]:
        return {line_of[int(record_id)] for record_id in entry["recordids"]}

    attack_lines = {a["name"]: lines_of(a) for a in key["attacks"]}
    lookalike_lines = {item["name"]: lines_of(item) for item in key["benign_lookalikes"]}
    every_attack_line = set().union(*attack_lines.values())

    high = [i for i in detection.incidents if band(i.confidence) == "High"]
    return FileResult(
        name=name,
        lines=len(rows),
        attacks=[_attack(n, lines, detection) for n, lines in attack_lines.items()],
        lookalikes=[_lookalike(n, lines, detection) for n, lines in lookalike_lines.items()],
        high_incidents=len(high),
        high_incidents_with_attack=sum(
            any(set(f.line_nos) & every_attack_line for f in i.findings) for i in high
        ),
        ml_ran=detection.ml_ran,
        ml_top_hours=_ml_hours(detection, attack_lines, lookalike_lines),
    )


def _attack(name: str, lines: set[int], detection: Detection) -> AttackResult:
    touching = [
        incident
        for incident in detection.incidents
        if any(set(f.line_nos) & lines for f in incident.findings)
    ]
    best = max(touching, key=lambda i: i.confidence, default=None)
    detectors = sorted({
        f.detector for i in touching for f in i.findings if set(f.line_nos) & lines
    })  # fmt: skip
    return AttackResult(
        name=name,
        lines=len(lines),
        flagged_lines=len(lines & detection.entry_scores.keys()),
        confidence=best.confidence if best else 0.0,
        severity=best.severity if best else 0,
        detectors=detectors,
    )


def _lookalike(name: str, lines: set[int], detection: Detection) -> LookalikeResult:
    scores = [detection.entry_scores[line][0] for line in lines if line in detection.entry_scores]
    detectors = sorted({f.detector for f in detection.findings if set(f.line_nos) & lines})
    return LookalikeResult(name, len(lines), max(scores, default=0.0), detectors)


def _ml_hours(
    detection: Detection, attacks: dict[str, set[int]], lookalikes: dict[str, set[int]]
) -> list[tuple[str, str, str]]:
    """What each Isolation Forest finding really was, according to the answer key."""
    hours = []
    for finding in (f for f in detection.findings if f.detector == "isolation_forest"):
        lines = set(finding.line_nos)
        # Label it by whichever planted pattern covers most of its lines.
        candidates = [(len(lines & al), f"attack: {n}") for n, al in attacks.items()]
        candidates += [(len(lines & ll), f"look-alike: {n}") for n, ll in lookalikes.items()]
        overlap, label = max(candidates, default=(0, ""))
        truth = label if overlap else "normal traffic"
        hours.append((finding.subject, f"{finding.start_ts:%H}:00", truth))
    return hours


# --- Markdown ----------------------------------------------------------------------------


def to_markdown(results: list[FileResult]) -> str:
    out = [
        "# Detection results",
        "",
        "Generated by `make evaluate` (`python -m app.evaluation`): every committed sample is",
        "parsed and analysed exactly as an upload would be, then compared with its answer key",
        "(`samples/*.ground_truth.json`). **Caught** means the attack's lines are in a",
        "High-confidence incident (≥ 0.8). A test fails if this file is out of date.",
        "",
        "## Summary",
        "",
        "| File | Lines | Attacks caught (High) | High incidents that are real | "
        "Look-alikes reaching High | Isolation Forest |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        caught = sum(a.caught for a in r.attacks)
        precision = (f"{r.high_incidents_with_attack} / {r.high_incidents}"
                     if r.high_incidents else "— (none)")  # fmt: skip
        lookalikes_high = sum(band(lk.highest_confidence) == "High" for lk in r.lookalikes)
        ml = "ran" if r.ml_ran else "skipped (< 200 active user-hours)"
        out.append(
            f"| `{r.name}` | {r.lines:,} | {caught} / {len(r.attacks)} | {precision} | "
            f"{lookalikes_high} / {len(r.lookalikes)} | {ml} |"
        )

    for r in results:
        out += ["", f"## `{r.name}`", ""]
        if r.attacks:
            out += [
                "| Attack | Caught | Incident confidence | Severity | Lines flagged | "
                "Detectors that fired |",
                "|---|---|---|---|---|---|",
            ]
            for a in sorted(r.attacks, key=lambda a: -a.confidence):
                out.append(
                    f"| {a.name.replace('_', ' ')} | {'✅' if a.caught else '❌'} | "
                    f"{a.confidence:.2f} | {SEVERITY.get(a.severity, '—')} | "
                    f"{a.flagged_lines} / {a.lines} | {', '.join(a.detectors) or '—'} |"
                )
            out.append("")
        out += [
            "| Benign look-alike | Highest band on its lines | Highest confidence | "
            "Detectors that fired |",
            "|---|---|---|---|",
        ]
        for lk in r.lookalikes:
            level = band(lk.highest_confidence) if lk.highest_confidence else "not flagged"
            out.append(
                f"| {lk.name.replace('_', ' ')} | {level} | {lk.highest_confidence:.2f} | "
                f"{', '.join(lk.detectors) or '—'} |"
            )
        if r.ml_ran:
            out += [
                "",
                f"**Isolation Forest on its own** (no rules): {r.ml_attacks} of its "
                f"{len(r.ml_top_hours)} most unusual user-hours are planted attacks.",
                "",
                "| User | Hour | What it really was |",
                "|---|---|---|",
            ]
            for user, hour, truth in r.ml_top_hours:
                out.append(f"| {user} | {hour} | {truth.replace('_', ' ')} |")
    return "\n".join(out) + "\n"


def main() -> None:
    sys.stdout.write(to_markdown([evaluate_file(name) for name in SAMPLE_FILES]))


if __name__ == "__main__":
    main()
