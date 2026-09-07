#!/usr/bin/env bash
# Deploy the TRUCK-A-FY engine to Cloud Run. Run from the repo root; keys come from .env (gitignored).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$HERE/.env" ]; then set -a; . "$HERE/.env"; set +a; fi
: "${ELEVENLABS_API_KEY:?set ELEVENLABS_API_KEY in .env}"
: "${ELEVEN_VOICE_ID:?set ELEVEN_VOICE_ID in .env}"
PROJECT=${PROJECT:-gen-lang-client-0287073066}
REGION=${REGION:-us-central1}
gcloud config set project "$PROJECT" >/dev/null
echo "style: ${LOGO_STYLE:-fire}"
gcloud run deploy truckafy-engine \
  --source . --quiet \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi --cpu 2 --concurrency 2 --timeout 300 \
  --set-env-vars "ELEVENLABS_API_KEY=$ELEVENLABS_API_KEY,ELEVEN_VOICE_ID=$ELEVEN_VOICE_ID,APP_SECRET=${APP_SECRET:-},LOGO_STYLE=${LOGO_STYLE:-fire}"
URL=$(gcloud run services describe truckafy-engine --region "$REGION" --format='value(status.url)')
echo; echo "LIVE: $URL"
echo "$URL" > .service_url
