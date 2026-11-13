#!/usr/bin/env bash
# Build and deploy everything, in an order that never serves new code against an old schema:
#   1. build the API image (Cloud Build: Linux/amd64, since Cloud Run doesn't run ARM images)
#   2. run database migrations as a one-off Cloud Run Job with the same image
#   3. roll out the API to Cloud Run
#   4. build the frontend and publish it on Firebase Hosting (which proxies /api to Cloud Run)
# Run with: make deploy
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$(dirname "$0")/../.."

TAG="$(git rev-parse --short HEAD)$(git diff --quiet HEAD -- backend || echo -dirty)"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$REPO/api:$TAG"
COMMON=(--region "$REGION" --project "$PROJECT" --service-account "$RUNNER"
        --set-env-vars "FIREBASE_PROJECT_ID=$PROJECT")

echo "1/4  Building $IMAGE…"
gcloud builds submit backend --tag "$IMAGE" --project "$PROJECT"

echo "2/4  Migrating the database…"
gcloud run jobs deploy migrate --image "$IMAGE" "${COMMON[@]}" \
  --set-secrets "DATABASE_URL=$SECRET_DIRECT:latest" \
  --command alembic --args upgrade,head --max-retries 0 --task-timeout 300 --quiet
gcloud run jobs execute migrate --region "$REGION" --project "$PROJECT" --wait

echo "3/4  Deploying the API…"
# 1 vCPU / 2 GiB fits pandas + scikit-learn; max 2 instances caps any runaway cost; scale to
# zero when idle (first request after a pause is a cold start); startup CPU boost shortens it.
gcloud run deploy api --image "$IMAGE" "${COMMON[@]}" \
  --set-secrets "DATABASE_URL=$SECRET_POOLED:latest" \
  --cpu 1 --memory 2Gi --concurrency 8 --min-instances 0 --max-instances 2 \
  --timeout 120 --cpu-boost --allow-unauthenticated --quiet

echo "4/4  Building and publishing the frontend…"
(cd frontend && npm ci --no-audit --no-fund && npm run build)
npx --yes firebase-tools@15.34.2 deploy --only hosting --project "$PROJECT"

echo "Live at https://$SITE.web.app"
