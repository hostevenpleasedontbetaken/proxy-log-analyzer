# Decisions

The design was settled phase by phase before any code was written. Each table lists the pick and why.

## Scope

| Decision | Why |
|---|---|
| No LLM at runtime; $0 to run | "AI-based threat detection" is met by Isolation Forest (unsupervised ML). Deterministic, free, no prompt-injection surface. LLM triage is future work. |
| Functional prototype over production-ready | Matches the assignment; production hardening is listed in the README instead. |

## Phase 1 — Log format and samples

| Decision | Why |
|---|---|
| Zscaler NSS web logs, NDJSON in Elastic's v12 `zscalernss-web` envelope (bare events and syslog prefix also accepted) | A real SOC log source with a documented schema |
| ~33 curated fields; `b64url` fields decoded; `epochtime` is the time source of truth | Enough for detection without storing every vendor field |
| Seeded behaviour-simulation generator, independent of the backend | Reproducible samples that don't share bugs with the parser |
| 8 labelled scenarios + benign look-alikes, `ground_truth.json` keyed by `recordid` | Lets us measure detection, including false positives |
| 25 MB upload cap; `.gz` accepted | Fits Cloud Run and Hosting limits |

## Phase 2 — Data model

| Decision | Why |
|---|---|
| 6 tables: `uploads`, `upload_files`, `log_entries`, `anomalies`, `anomaly_entries`, `incidents` | Minimal set that covers upload → entries → flags → incidents |
| No users table; `owner_uid` comes from Firebase | Firebase already owns identity |
| Raw file gzipped in `upload_files` (bytea, 1:1); no per-row raw JSON copy | Keeps the original without doubling storage |
| `log_entries` PK `(upload_id, line_no)`, one shared table, denormalized `anomaly_confidence` / `max_severity` | Fast highlighting without joins |
| Stats computed once into `uploads.stats` (JSONB) | Overview loads instantly |
| Dedupe on `(owner_uid, sha256)`; `inet` IPs; offset pagination; severity smallint 1–4 | Simple and correct at prototype scale |
| Partitioning by upload = documented scale-up path only | Not needed at 100k rows per upload |

## Phase 3 — API and auth

| Decision | Why |
|---|---|
| 10 REST endpoints under `/api` | `health`, `me`, uploads (create, list, get, delete), entries list + detail, incidents, anomalies |
| Firebase ID token as `Authorization: Bearer`, verified in a blueprint-wide `before_request` | One check covers every route |
| Not your upload → 404; 401 only for a bad token | Prevents IDOR and doesn't reveal what exists |
| Email + password, public sign-up off, private demo account | Reviewer access without open registration |
| Pydantic v2 validation; error envelope `{"error":{"code","message"}}`; snake_case; ISO UTC | Predictable contract for the frontend |
| Synchronous upload; 409 + `existing_upload_id` on duplicates | Simplest flow that fits within 60 s |
| Limits: 25 MB body, 50 MB unzipped, 100k lines, page_size ≤ 200 | Bounded work per request |
| App refuses to start with the Auth emulator env set on Cloud Run | Emulator tokens can never be accepted in production |
| XSS: React escaping only, `react/no-danger` lint rule, log URLs shown as text (never links), CSP, session-only login persistence | Log content is attacker-controlled |
| Bearer tokens over session cookies (CSRF noted as production hardening) | No CSRF surface; simpler for a prototype |

## Phase 4 — Parsing and stats

| Decision | Why |
|---|---|
| Streaming generator pipeline: unzip → lines → strip syslog → JSON → unwrap envelope → field converters | Constant memory per line; each step testable |
| Bad field → NULL + counted warning; bad line → skipped + counted; >50 % bad or failed sniff → 422 | Tolerant of messy logs, strict about the wrong file type |
| Sniff: first 50 lines, 80 % must be web events → `not_zscaler_web` | Clear error for non-Zscaler uploads |
| Strip NUL; cap URL 8 KB, other fields 1 KB | Postgres safety and bounded storage |
| `epochtime` first, fallback `time` + tz, warn on > 60 s mismatch | Vendor docs show the two can disagree |
| pandas DataFrame shared by stats and detection; `COPY` insert | Fast aggregation and bulk insert |
| Timeline auto-buckets (1m … 1d), ≤ 200 buckets, zero-filled; top-10 + other; UTC display | Readable chart at any file duration |

## Phase 5 — Detection

| Decision | Why |
|---|---|
| Three layers: rules → per-user stats (median/MAD) → Isolation Forest | Known-bad, unusual-for-this-user, and unknown-unknowns |
| 13 detectors mapped to the 8 scenarios + benign look-alikes | Every scenario covered; look-alikes test false positives |
| Confidence via per-detector curves; max within a family, noisy-OR across families; severity separate | Agreement between independent signals raises confidence |
| Bands High ≥ 0.8 / Medium / Low; noise floor 0.3 | Keeps the UI focused |
| Incidents = same subject within 30 min | Groups related flags into one story |
| Isolation Forest on active user-hour rows (≥ 10 requests), 10 features, 200 trees, `max_samples` 256, `contamination` auto, `random_state` 42, refit per upload, skipped below 200 active user-hours | Unsupervised, explainable via the most extreme features |
| IF flags only past sklearn's threshold **and** in the top 1 %; its own confidence ≤ 0.70, ML-only incidents capped at 0.75 | Unusual ≠ malicious; High needs a second detector to agree |
| Evaluation vs `ground_truth.json` (`make evaluate` → `docs/RESULTS.md`, kept current by a test), reporting IF-only and combined | Proves detection with numbers |

## Phase 6 — Frontend

| Decision | Why |
|---|---|
| Routes `/login`, `/uploads`, `/uploads/:id?tab=overview\|incidents\|entries` | Matches the SOC flow: summary → what to look at → evidence |
| React Router; TanStack Query for server state, `useState` for UI state | Caching, race safety and invalidation for free |
| URL search params are the single source of truth for filters, page, tab | Shareable links; table and timeline stay in sync |
| shadcn Table, server pagination 100/page | Never loads 100k rows |
| Highlight = row tint + left bar + text badge ("High 86%") | Works for colour-blind users |
| Drawer "Why flagged": one sentence per detector + "this hour vs typical" numbers | Explanations a human can check |
| Recharts: allowed/blocked stacked bars, flagged entries in a second hover-synced chart (no dual axis), table view; click a bar to see its entries | Timeline drives investigation |
| react-dropzone + XHR progress, then "Analyzing…"; "Try a sample" buttons | Real progress; one-click demo |
| Overview tiles and incident/finding links drill into the filtered tab; the upload page is lazy-loaded so the chart library isn't in the login bundle | Summary → evidence in one click; faster first load |
| Vitest + Testing Library for logic, components and URL state; end-to-end flows checked in a real browser at each step (Playwright left as future work) | Signal without a heavy suite |

## Phase 7 — Docker and local dev

| Decision | Why |
|---|---|
| Compose runs db, auth emulator, migrate, api, web | One command, no accounts needed |
| One backend Dockerfile (python 3.13-slim, uv, non-root, gunicorn); compose overrides to `flask --debug` | Local runs the production image |
| Firebase Auth emulator with project `demo-tenex` and a seeded demo user | Real token checks offline |
| One-shot `migrate` service before `api` | Clear ordering; mirrors production |
| `.env` gitignored, `.env.example` committed | Standard; local-only values |
| pytest against a separate `tenex_test` DB in the same Postgres | Real COPY / inet / JSONB behaviour |
| Ports 5173 web, 8080 api (5000 is AirPlay on macOS), 5433 db (5432 is often a local Postgres), 9099 auth, 4000 emulator UI; all bound to 127.0.0.1 | Avoids common clashes |

## Phase 8 — Deploy

| Decision | Why |
|---|---|
| Firebase Hosting + Cloud Run (`us-east1`) + Neon (`aws-us-east-1`) | Free tiers; same-origin `/api` so no CORS |
| Image built by Cloud Build | Mac is ARM, Cloud Run is amd64 |
| `make deploy`: build → migrate job → deploy service → deploy hosting; GitHub Actions for CI only | Simple and repeatable |
| Cloud Run 1 vCPU / 2 GiB, max 2 instances, min 0, Startup CPU Boost | Fits the free tier; caps runaway cost |
| 10 uploads per user | Neon Free has 1 GB |
| $1 budget alert, Artifact Registry keeps latest image, dedicated `api-runner` service account | Cost and least-privilege guardrails |
| Skeleton deploy early, including a 25 MB upload through Hosting | Finds limits while they're cheap to fix |

## Phase 9 — Deliverables

| Decision | Why |
|---|---|
| README with a requirements → where table above the fold; depth in `docs/` | Reviewer can verify in two minutes |
| `docs/AI.md`: detection approach + how AI was used to build it | Meets the requirement; honest about tooling |
| 4 committed sample files + ground truth + generator | Ready to use and reproducible |
| ~5 min video, demo first | Shows the product before the architecture |
| Private repo + invite; demo credentials sent by email | Keeps the work and credentials private |
