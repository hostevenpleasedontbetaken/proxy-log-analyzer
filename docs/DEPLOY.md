# Deploying

Production runs entirely on free tiers:

```
browser ─► Firebase Hosting (React build, CDN) ── /api/** rewrite ──► Cloud Run "api" (us-east1)
                                                                       └─► Neon Postgres (aws-us-east-1)
Cloud Run Job "migrate" (same image) ─► Neon, direct connection, before each API rollout
Secret Manager: the two Neon connection strings, readable only by the api-runner service account
```

Because the browser only ever talks to the `web.app` domain, `/api` is same-origin: no CORS.

## One-time setup

Prerequisites: a Firebase project on the Blaze plan (billing account attached; usage stays in
the free tier), a Neon project, and the `gcloud` CLI logged in (`gcloud auth login`).

```bash
make cloud-setup     # APIs, image registry + cleanup policy, service account, empty secrets
make cloud-secrets   # paste the pooled and the direct Neon connection strings (hidden input)
npx firebase-tools login
```

## Each deploy

```bash
make deploy
```

1. **Build** the API image with Cloud Build (Linux/amd64; a Mac builds ARM images, which
   Cloud Run can't run) and push it to Artifact Registry.
2. **Migrate** the database with a one-off Cloud Run Job using the same image and Neon's
   direct connection (migrations need a real session; the pooler can't hold one).
3. **Deploy the API** to Cloud Run: 1 vCPU, 2 GiB, 2 workers × 4 threads, scale to zero,
   at most 2 instances, startup CPU boost, Neon's pooled connection.
4. **Build the frontend** with `frontend/.env.production` and publish it to Firebase Hosting.

## Cost guardrails

| Guardrail | Why |
|---|---|
| `--max-instances 2` | Caps what a traffic spike or a loop could ever run |
| `--min-instances 0` | Nothing runs (or bills) while idle; the first request after a pause is a cold start |
| Uploads need a signed-in user; public sign-up is off | Strangers can't create load |
| 10 uploads per user, 25 MB per upload | Keeps Neon under its 1 GB free storage |
| Artifact Registry cleanup policy | Keeps only the newest images (0.5 GB free) |
| $1 budget alert (set in the console) | Early warning; budgets alert, they don't stop spending |

## Production settings that differ from local

| Setting | Local (docker compose) | Production |
|---|---|---|
| Firebase Auth | Emulator (`demo-tenex`) | Real project; the API refuses to start if the emulator variable is set on Cloud Run |
| Database | Postgres 18 container | Neon (Postgres 18) |
| Server | Flask debug server, auto-reload | gunicorn |
| Frontend | Vite dev server + proxy | Static build on Hosting + rewrite |
