# TENEX Log Analyzer

Upload Zscaler web proxy logs → get a SOC timeline, incidents, and anomaly flags with
explanations and confidence scores.

> 🚧 In progress. See [docs/ROADMAP.md](docs/ROADMAP.md) for the build plan and
> [docs/DECISIONS.md](docs/DECISIONS.md) for why things are the way they are.

## Run locally

Requires Docker only.

```bash
docker compose up --build
```

Open http://localhost:5173 and sign in with the local demo account from
[`.env.example`](.env.example) (it only exists in the local Firebase Auth emulator).
