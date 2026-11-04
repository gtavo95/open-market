#!/usr/bin/env bash
# Deploys the public demo to its own Cloud Run service. It touches nothing else in the project.
#
# One instance: the sessions and the turn cap live in the process. One kept warm, so a judge's
# conversation does not vanish when the service scales to zero. The secrets must exist first:
#
#   scripts/deploy.sh secrets    once, reads .env without printing it
#   scripts/deploy.sh            builds and deploys
set -euo pipefail

SERVICE=open-market
REGION=europe-west1
PROJECT=chats-444205
RUNNER=28985494187-compute@developer.gserviceaccount.com

secret() {
  local name=$1 key=$2
  sed -n "s/^$key=//p" .env | tr -d '\n' |
    gcloud secrets create "$name" --project "$PROJECT" --replication-policy=automatic --data-file=-
  gcloud secrets add-iam-policy-binding "$name" --project "$PROJECT" --format=none \
    --member="serviceAccount:$RUNNER" --role=roles/secretmanager.secretAccessor
}

if [[ "${1:-}" == secrets ]]; then
  secret OPEN_MARKET_MUSE_API_KEY MUSE_API_KEY
  secret OPEN_MARKET_TYPESAFE_API_KEY TYPESAFE_API_KEY
  exit
fi

gcloud run deploy "$SERVICE" --project "$PROJECT" --region "$REGION" --source . \
  --port 8000 --memory 1Gi --cpu 1 --timeout 300 \
  --min-instances 1 --max-instances 1 --allow-unauthenticated \
  --set-secrets MUSE_API_KEY=OPEN_MARKET_MUSE_API_KEY:latest,TYPESAFE_API_KEY=OPEN_MARKET_TYPESAFE_API_KEY:latest
