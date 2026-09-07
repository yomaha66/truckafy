#!/usr/bin/env bash
# Deploy the TRUCK-A-FY engine to Cloud Run. Run from ~/truckafy in Cloud Shell (source ~/.truckafy_env first).
set -euo pipefail
: "${ELEVENLABS_API_KEY:?export ELEVENLABS_API_KEY first}"
: "${ELEVEN_VOICE_ID:?export ELEVEN_VOICE_ID first}"
PROJECT=${PROJECT:-gen-lang-client-0287073066}
REGION=${REGION:-us-central1}
gcloud config set project "$PROJECT" >/dev/null
gcloud run deploy truckafy-engine \
  --source . --quiet \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 2Gi --cpu 2 --concurrency 2 --timeout 300 \
  --set-env-vars "ELEVENLABS_API_KEY=$ELEVENLABS_API_KEY,ELEVEN_VOICE_ID=$ELEVEN_VOICE_ID,APP_SECRET=${APP_SECRET:-},LOGO_STYLE=${LOGO_STYLE:-fire}"
URL=$(gcloud run services describe truckafy-engine --region "$REGION" --format='value(status.url)')
echo; echo "LIVE: $URL"
echo "$URL" > .service_url
