# Implementation roadmap

Each milestone ships as one or more **small PRs** (one concern each), reviewed and merged
before dependent work is opened. Tag the last merge of each milestone (`m0`, `m1`, …).
The reasoning behind every choice is in [DECISIONS.md](DECISIONS.md).

M0 is split into: `m0-docs` (this plan) · `m0-backend` (Flask skeleton) · `m0-frontend`
(React skeleton) · `m0-compose` (docker compose + emulator, opened after backend + frontend merge).

| # | Branch | Delivers | Done when |
|---|---|---|---|
| M0 | `m0-scaffold` | Repo layout, Flask app with `/api/health` + Firebase token check, Vite/React/TS/Tailwind/shadcn app with login + protected route, Dockerfile, docker compose (db, auth emulator, migrate, api, web), Makefile, CI workflow | `docker compose up` → log in as the demo user → page shows the API's "hello, &lt;uid&gt;" |
| M1 | `m1-deploy-skeleton` | Firebase project, Neon, Cloud Run service + migrate job, Secret Manager, `make deploy`, budget alert | Live `web.app` link logs in and a 25 MB test upload through Hosting succeeds in < 60 s |
| M2 | `m2-samples` | Seeded `samples/generate.py`, 8 scenarios + benign look-alikes, ground truth, the 4 committed sample files, `samples/README.md` | `make samples` regenerates byte-identical files |
| M3 | `m3-data-model` | SQLAlchemy models for the 6 tables + first Alembic migration | `alembic upgrade head` on a fresh DB; model tests pass |
| M4 | `m4-parsing-api` | Streaming parser, stats, COPY insert, all 9 endpoints, error envelope, limits, dedupe, upload quota | Upload a sample via curl → stats + paginated entries come back; 422 for `not-zscaler.log` |
| M5 | `m5-detection` | Rules, stats (median/MAD), Isolation Forest, confidence combining, incidents, eval vs ground truth | pytest eval meets targets; per-scenario table printed |
| M6 | `m6-frontend` | Uploads page, Overview / Incidents / Entries tabs, drawer, timeline, highlighting, "Try a sample" | Playwright smoke: login → sample upload → High incident visible |
| M7 | `m7-deliverables` | README, docs/AI.md, screenshots, final checklist, video | Fresh clone + compose works; live link works in incognito; gitleaks clean |

## Needs you (can't be done by Claude)

| When | What |
|---|---|
| Before M1 | Create a Google Cloud / Firebase project and attach a billing account (card); create a Neon account; install `gcloud` and `firebase` CLIs and log in |
| Before M1 | Create the GitHub repo (private) — or tell Claude to create it with `gh` |
| M1 | Create the real demo user in the Firebase console; untick "Enable create (sign-up)" |
| M7 | Record the video; send the invite to venkata@tenex.ai and the demo credentials |
