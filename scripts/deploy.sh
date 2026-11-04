#!/usr/bin/env bash
# Deploys the public demo to a Cloud Run service. It touches nothing else in the project.
#
#   scripts/deploy.sh secrets    once, reads .env without printing it
#   scripts/deploy.sh            builds and deploys the `open-market` service
#   scripts/deploy.sh demo       updates the settings of `demo`; its image comes from a push to main
#
# open-market: at most one instance, because the sessions and the turn cap live in the process.
# It scales to zero, so a conversation vanishes when it goes idle. The secrets
# (`scripts/deploy.sh secrets`) must exist first.
#
# demo: a service that already has its own env and secret mounts (ENV, ISSUER, DEMO_SECRET,
# TYPESAFE_API_KEY, ...). Only `--update-*` flags go here: `--set-env-vars` or `--set-secrets` would
# wipe all of that. What it changes: PROVIDER=muse (the old PROVEEDOR is ignored by the app) and the
# Muse key, mounted as MUSE_API_KEY from OPEN_MARKET_MUSE_API_KEY. It scales to zero, so a cold
# start forgets the conversations. Port, CPU, timeout, max instances, concurrency and
# the invoker setting stay as the service has them.
#
#   MEMORY=256Mi scripts/deploy.sh demo     overrides the 512Mi default; below 512Mi it runs on gen1
#   DRY_RUN=1 scripts/deploy.sh demo      prints the gcloud command and runs nothing
#
# Under 512Mi the second generation environment is not allowed (it needs at least 512Mi), so
# the script pins the first one then. CPU stays at 1.
set -euo pipefail

TARGET=${1:-open-market}
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

case "$TARGET" in
  secrets)
    secret OPEN_MARKET_MUSE_API_KEY MUSE_API_KEY
    secret OPEN_MARKET_TYPESAFE_API_KEY TYPESAFE_API_KEY
    exit
    ;;
  open-market)
    flags=(
      --port 8000 --memory 1Gi --cpu 1 --timeout 300
      --min-instances 0 --max-instances 1 --allow-unauthenticated
      --set-secrets MUSE_API_KEY=OPEN_MARKET_MUSE_API_KEY:latest,TYPESAFE_API_KEY=OPEN_MARKET_TYPESAFE_API_KEY:latest
    )
    ;;
  demo)
    MEMORY=${MEMORY:-512Mi}
    if [[ ! $MEMORY =~ ^[0-9]+(Mi|Gi)$ ]]; then
      echo "MEMORY=$MEMORY: use a whole number with Mi or Gi, like 512Mi" >&2
      exit 2
    fi
    flags=(
      --memory "$MEMORY" --min-instances 0
      --update-env-vars PROVIDER=muse
      --update-secrets MUSE_API_KEY=OPEN_MARKET_MUSE_API_KEY:latest
    )
    if [[ $MEMORY =~ ^([0-9]+)Mi$ ]] && ((BASH_REMATCH[1] < 512)); then
      flags+=(--execution-environment gen1)
    fi
    ;;
  *)
    echo "usage: scripts/deploy.sh [secrets|open-market|demo]" >&2
    exit 2
    ;;
esac

# The image of `demo` comes from the Cloud Build trigger on a push to main; here only its settings.
if [[ $TARGET == demo ]]; then
  cmd=(gcloud run services update demo --project "$PROJECT" --region "$REGION" "${flags[@]}")
else
  cmd=(gcloud run deploy "$TARGET" --project "$PROJECT" --region "$REGION" --source . "${flags[@]}")
fi

if [[ -n "${DRY_RUN:-}" ]]; then
  printf '%q ' "${cmd[@]}"
  echo
  exit
fi

"${cmd[@]}"
