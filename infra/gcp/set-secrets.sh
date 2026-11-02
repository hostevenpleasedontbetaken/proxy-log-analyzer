#!/usr/bin/env bash
# Store the two Neon connection strings in Secret Manager. Typing is hidden and the values go
# straight to Google: they're never printed, written to a file, or put in the repo.
# Run with: make cloud-secrets
set -euo pipefail
source "$(dirname "$0")/config.sh"

store() {
  local secret=$1 prompt=$2 value
  read -r -s -p "$prompt: " value
  echo
  [[ $value == postgresql://* ]] || { echo "That doesn't look like a postgresql:// URL." >&2; exit 1; }
  printf %s "$value" | gcloud secrets versions add "$secret" --data-file=- --project "$PROJECT" >/dev/null
  echo "  saved a new version of $secret"
}

echo "From the Neon console → your project → Connect:"
store "$SECRET_POOLED" "Connection string WITH connection pooling (host contains -pooler)"
store "$SECRET_DIRECT" "Connection string WITHOUT pooling (direct)"
