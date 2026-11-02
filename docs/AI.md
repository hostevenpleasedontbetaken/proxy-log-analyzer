# AI approach

Two parts: how the app detects threats (the "AI-based threat detection" requirement), and how
AI tools were used to build it.

## Detection at a glance

Detection runs once per upload, on the parsed log as a pandas DataFrame: pure Python, no
network calls, deterministic. It has three layers, each catching what the previous one can't:

| Layer | Detectors | Catches | Example |
|---|---|---|---|
| 1. Rules | 6 | What Zscaler already marked as bad, plus near-certain patterns | "Zscaler identified Trojan.Win32.Emotet in 2 requests…" |
| 2. Statistics | 6 | Behaviour unusual *for this user*, against a baseline learned from the same file | "uploaded 146 MB in the 23:00 hour, 22,267× their typical hour" |
| 3. Isolation Forest (ML) | 1 | User-hours unusual in a *combination* nobody wrote a rule for | "errors 45% vs typical 3%; randomness of host names 3.3 vs 1.7" |

```
log rows ─┬─ rules ───────────┐
          ├─ statistics ──────┼─► findings ─► incidents (same user, within 30 min)
          └─ Isolation Forest ┘     │               └─► combined confidence + severity
                                    └─► per-entry score (for highlighting in the table)
```

Every finding carries a one-sentence explanation with the actual numbers, a confidence
(0–1, "how sure"), a severity (Low → Critical, "how bad if real"), and the exact log lines it
is about, so an analyst can check the claim against the evidence.

## Layer 1: rules

| Detector | Fires when | Confidence |
|---|---|---|
| `known_threat` | Zscaler named a threat (virus, trojan…) in the traffic | 0.95 |
| `phishing_post` | A phishing page was opened and a form was sent to the same host within 5 minutes (credentials likely entered) | 0.90, Critical |
| `high_risk_score` | Zscaler's page risk score is 75 or more | 0.5 at 75 → 0.9 at 100 |
| `risky_category` | Phishing / malware / spyware sites; anonymizers scale with the number of attempts | 0.4–0.85 |
| `repeated_blocks` | 10+ blocked requests in a burst (someone trying to get around policy) | 0.6–0.85 |
| `script_user_agent` | Traffic from `curl`, `python-requests`, `wget`… instead of a browser | 0.35 (weak alone; IT does this too) |

## Layer 2: statistics

There is no history, and the attack is inside the data, so baselines are learned from the file
itself using the **median** and **MAD** (median absolute deviation) rather than mean and
standard deviation: one huge upload barely moves a median but drags an average far up.

| Detector | Fires when | What keeps its benign twin quiet |
|---|---|---|
| `beaconing` | One device calls one host on a near-fixed timer (low variation in gaps *and* sizes) | Hosts most of the company contacts (security agent, update checks) are skipped |
| `exfil_volume` | A user uploads ≥ 20 MB in an hour and ≥ 10× their typical hour; the rows to the top destination are flagged | Uploads to sanctioned business apps (company storage) count half and stay Low severity |
| `burst` | Requests per minute ≥ max(60, 10× the typical rate); ≥ 50% 404s means scanning | — |
| `off_hours` | Browser traffic well outside the user's workday, which is learned from their busiest cluster of hours | Only browser user agents count, so background software at night doesn't |
| `new_device` | A login appears from a minority device; each difference (IP, browser, location) adds weight | Alone it stays Medium: people do get new laptops |
| `random_domains` | 10+ never-seen, random-looking host names tried within 10 minutes, most never answering (malware DGA) | — |

## Layer 3: Isolation Forest

**Why it's here:** rules and statistics only find what someone thought to look for. An
Isolation Forest is unsupervised: it needs no labelled attacks, and it ranks how *isolated*
each data point is. It builds many random trees that split the data with random questions
("bytes out > 40 MB?"); ordinary points take many splits to separate from the crowd, while
odd points are isolated in a few.

| Setting | Value | Why |
|---|---|---|
| Unit | One row per user per **active** hour (≥ 10 requests) | Idle laptops at night (a few background requests) made every ordinary working hour look odd |
| Features (10) | requests; log of bytes uploaded / downloaded; distinct hosts; share of never-seen hosts; shares of blocked, error (4xx/5xx), POST/PUT and scripted requests; mean host-name randomness (entropy) | Volume, destination, policy, tooling and timing in one row. Logs tame MB-scale differences; ratios are smoothed as `count / (requests + 10)` so 1 block in 4 requests isn't "25% blocked" |
| Model | `IsolationForest(n_estimators=200, max_samples=256, contamination="auto", random_state=42)`, fitted fresh per upload | Fixed seed → identical results every run (tested) |
| Minimum data | Skipped below 200 active user-hours, and the UI says so | Too little data to learn "normal" (the small and clean samples) |
| Flagged | Past scikit-learn's outlier threshold **and** among the oddest 1% | Bounds how much it can report |
| Explanation | The 3 features furthest from the typical active hour (robust z-score), in words: "bytes uploaded 145.7 MB vs typical 0.03 MB" | A model score alone can't be checked by an analyst |
| Highlighted rows | Only the rows behind its top feature (e.g. the large uploads, not the whole hour) | Points the analyst at the evidence |
| Confidence | Up to 0.70 on its own | **Unusual isn't malicious.** ML alone can never reach High; it raises confidence when another detector agrees about the same person |

## Combining evidence

Each finding belongs to an **evidence family** (known-bad, policy, tooling, volume, rate,
timing, identity, destination, ML). An ML finding joins the family of the feature it found
most unusual, so a huge upload reported by both `exfil_volume` and the forest counts once.

Confidence for an incident = strongest finding per family, then a **noisy-OR** across families,
i.e. 1 − (the chance every independent family is a false alarm). Example, the DGA incident:

| Family | Strongest finding | Confidence |
|---|---|---|
| destination | `random_domains` | 0.90 |
| timing | `beaconing` | 0.77 |
| rate | Isolation Forest (top feature: error share) | 0.70 |
| **Combined** | 1 − (0.10 × 0.23 × 0.30) | **0.99** |

- **Bands:** High ≥ 0.8, Medium ≥ 0.5, Low below; findings under 0.3 are dropped as noise.
- **ML alone is capped at 0.75**, below High.
- **Severity is separate** from confidence and is the worst severity of the incident's findings.
- **Incidents** group findings about the same subject that start within 30 minutes of each
  other, so a DGA burst followed by C2 check-ins reads as one story.

## Results

Measured against the samples' answer keys by `make evaluate`; the full tables are in
[RESULTS.md](RESULTS.md), and a test fails if they go stale.

| File | Attacks caught at High | High incidents that are real | Look-alikes reaching High |
|---|---|---|---|
| Full day (18,654 lines) | **8 / 8** | **7 / 7** | **0 / 4** |
| Small (1,934 lines) | 3 / 3 | 3 / 3 | 0 / 4 |
| Clean (4,608 lines, no attacks) | — | none | 0 / 4 |

**Isolation Forest on its own** (no rules or statistics): 4 of its 5 most unusual user-hours
are planted attacks (scanning, DGA, exfiltration, policy probing). The fifth is the
IT-automation look-alike, which the combined system keeps at Medium.

## Limitations

- **Synthetic data, designed alongside the detectors.** The samples come from a seeded
  generator written independently of the backend, with benign look-alikes for each attack and
  a clean file, but the same project wrote both. Treat the numbers above as an upper bound;
  real validation needs labelled production logs.
- **Baselines come from one file.** With no history, a user who is always unusual looks normal,
  and a short file has little to learn from (hence the 200 user-hour minimum for ML).
- **Thresholds are hand-set** and documented in the code next to each detector; with real data
  they would be tuned against analyst feedback.
- **The forest always ranks something oddest.** The 1% cap and the ML-alone confidence cap keep
  that from becoming a High alert, but a benign outlier can still show up as Medium (the
  IT-automation hour does).
- **Gaps on the day sample:** the malware landing page itself isn't flagged (2 of 3 lines), and
  two look-alikes reach Medium. Both are listed in RESULTS.md.

## Why no LLM at runtime

| Concern | With an LLM in the detection path | This design |
|---|---|---|
| Cost | Per-upload API spend | $0: runs on the free tier |
| Reproducibility | Answers vary between runs | Same file → same findings (tested byte-for-byte) |
| Prompt injection | Log content is attacker-controlled (URLs, user agents, file names) and would be read by the model | No model reads log text |
| Explainability | Free-text reasoning that's hard to verify | Every finding cites the numbers and the exact rows |

A sensible next step is an LLM **on top of** the structured findings, not in place of them:
summarising an incident or suggesting next steps, with the evidence rows attached and a
human deciding.

## How AI was used to build this

The project was built with **Claude Code** (Anthropic's coding agent) as a pair programmer:

- **Decisions were made up front and by the author.** Each phase (log format, data model,
  API, parsing, detection, frontend, deploy) was discussed and decided before code was written,
  and recorded in [DECISIONS.md](DECISIONS.md).
- **Small, reviewed pull requests.** Claude Code wrote most of the code and tests; every change
  went through a pull request that the author reviewed and merged, one concern at a time.
- **Claims were checked, not trusted.** Detection quality is measured against independent
  answer keys rather than asserted, the UI was checked in a real browser at each step, and
  several bugs were found that way (for example an idle-hours effect that made ordinary
  workdays look unusual to the Isolation Forest).
