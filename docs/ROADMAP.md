# Implementation roadmap

Each milestone ships as one or more **small PRs** (one concern each), reviewed and merged
before dependent work is opened. Tag the last merge of each milestone (`m0`, `m1`, …).
The reasoning behind every choice is in [DECISIONS.md](DECISIONS.md).

**Status:** M0–M6 are merged and tagged; M7 (deliverables) is in progress.

| # | Branch(es) | Delivers | Done when |
|---|---|---|---|
| M0 | `m0-docs`, `m0-backend`, `m0-frontend`, `m0-compose`, `m0-ci` | This plan; Flask app with `/api/health` + Firebase token check; Vite/React/TS/Tailwind/shadcn app with login + protected route; Dockerfile; docker compose (db, auth emulator, migrate, api, web); Makefile; CI workflows | `docker compose up` → log in as the demo user → page shows the API's "hello, &lt;email&gt;" |
| M1 | `m1-deploy` | Firebase project, Neon, Cloud Run service + migrate job, Secret Manager, `make deploy`, budget alert | Live `web.app` link logs in and a 25 MB test upload through Hosting succeeds in < 60 s |
| M2 | `m2-samples` | Seeded `samples/generate.py`, 8 scenarios + benign look-alikes, ground truth, the 4 committed sample files, `samples/README.md` | `make samples` regenerates byte-identical files |
| M3 | `m3-data-model` | SQLAlchemy models for the 6 tables + first Alembic migration | `alembic upgrade head` on a fresh DB; model tests pass |
| M4 | `m4-parsing-api` | Streaming parser, stats, COPY insert, all 9 endpoints, error envelope, limits, dedupe, upload quota | Upload a sample via curl → stats + paginated entries come back; 422 for `not-zscaler.log` |
| M5 | `m5-detection` | Rules, stats (median/MAD), Isolation Forest, confidence combining, incidents, eval vs ground truth | pytest eval meets targets; per-scenario table printed |
| M6 | `m6-frontend` | Uploads page, Overview / Incidents / Entries tabs, drawer, timeline, highlighting, "Try a sample" | In a real browser: login → sample upload → High incident visible → its entries and why they were flagged |
| M7 | `m7-deliverables` | README, docs/AI.md, screenshots, final checklist, video | Fresh clone + compose works; live link works in incognito; gitleaks clean |

## Manual steps

Account, billing and console steps that happen outside the codebase.

| When | What |
|---|---|
| Before M1 | Create a Google Cloud / Firebase project and attach a billing account; create a Neon account; install the `gcloud` and `firebase` CLIs and log in |
| M1 | Create the real demo user in the Firebase console; untick "Enable create (sign-up)" |
| M7 | Record the video; share the demo credentials |
