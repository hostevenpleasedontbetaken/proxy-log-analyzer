"""Regenerate the committed sample files and their answer keys.

    python samples/build_samples.py     (or: make samples)

Each file's options live here, so the committed copies can always be reproduced exactly;
a test regenerates them and compares bytes.
"""

from pathlib import Path

import generate

SAMPLES_DIR = Path(__file__).resolve().parent

SAMPLE_FILES = {
    # The main demo: a full day, 40 employees, all eight attacks (~18.7k lines, 1 MB gzipped).
    "acme-web-day.ndjson.gz": ["--users", "40", "--attacks", "all"],
    # A quick first upload: 5 employees, three attacks (~1.9k lines).
    "acme-web-small.ndjson": [
        "--users", "5", "--attacks", "phishing,malware_download,data_exfiltration",
    ],
    # No attacks, only normal traffic and benign look-alikes: measures false alarms.
    "acme-web-clean.ndjson": ["--users", "12", "--attacks", "none"],
}  # fmt: skip


def build(out_dir: Path = SAMPLES_DIR) -> list[Path]:
    """Write every sample and its answer key into `out_dir`; returns the paths written."""
    written = []
    for name, options in SAMPLE_FILES.items():
        log = out_dir / name
        generate.main(["--out", str(log), *options])
        written += [log, generate.answer_key_path(log)]
    return written


if __name__ == "__main__":
    build()
