#!/usr/bin/env bash
# One-time Google Cloud setup (safe to re-run): APIs, image registry, the API's service
# account, and empty secrets for the Neon connection strings. Run with: make cloud-setup
set -euo pipefail
source "$(dirname "$0")/config.sh"

echo "1/5  Turning on the Google Cloud APIs we use…"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com iam.googleapis.com --project "$PROJECT"

echo "2/5  Image registry (keeps only the newest images, to stay in the 0.5 GB free tier)…"
gcloud artifacts repositories describe "$REPO" --location "$REGION" --project "$PROJECT" \
  >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPO" --repository-format docker \
    --location "$REGION" --project "$PROJECT" --description "TENEX log analyzer images"
gcloud artifacts repositories set-cleanup-policies "$REPO" --location "$REGION" \
  --project "$PROJECT" --policy "$(dirname "$0")/cleanup-policy.json" --no-dry-run

echo "3/5  Letting Cloud Build push images (new projects build as the Compute default account)…"
NUMBER=$(gcloud projects describe "$PROJECT" --format 'value(projectNumber)')
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member "serviceAccount:$NUMBER-compute@developer.gserviceaccount.com" \
  --role roles/cloudbuild.builds.builder --condition None >/dev/null

echo "4/5  The service account the API and migrations run as (least privilege)…"
gcloud iam service-accounts describe "$RUNNER" --project "$PROJECT" >/dev/null 2>&1 ||
  gcloud iam service-accounts create "${RUNNER%%@*}" --project "$PROJECT" \
    --display-name "TENEX API (Cloud Run)"

echo "5/5  Secrets for the Neon connection strings (values are added separately)…"
for secret in "$SECRET_POOLED" "$SECRET_DIRECT"; do
  gcloud secrets describe "$secret" --project "$PROJECT" >/dev/null 2>&1 ||
    gcloud secrets create "$secret" --replication-policy automatic --project "$PROJECT"
  # The API's service account may read these two secrets, and nothing else.
  gcloud secrets add-iam-policy-binding "$secret" --project "$PROJECT" \
    --member "serviceAccount:$RUNNER" --role roles/secretmanager.secretAccessor >/dev/null
done

echo "Done. Next: make cloud-secrets   (paste the two Neon connection strings; hidden input)"
