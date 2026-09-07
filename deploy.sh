#!/usr/bin/env bash
# Deploy the TRUCK-A-FY engine to Cloud Run. Run from ~/truckafy in Cloud Shell.
set -euo pipefail
: "${GEMINI_API_KEY:?export GEMINI_API_KEY first}"
if [ "${#GEMINI_API_KEY}" -lt 30 ]; then echo "GEMINI_API_KEY looks like a placeholder (len ${#GEMINI_API_KEY})"; exit 1; fi
PROJECT=${PROJECT:-gen-lang-client-0287073066}
REGION=${REGION:-us-central1}
gcloud config set project "$PROJECT" >/dev/null
gcloud run deploy truckafy-engine \
  --source . --quiet \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 1Gi --cpu 1 --concurrency 4 --timeout 180 \
  --set-env-vars "GEMINI_API_KEY=$GEMINI_API_KEY"
URL=$(gcloud run services describe truckafy-engine --region "$REGION" --format='value(status.url)')
echo; echo "LIVE: $URL"
echo "$URL" > .service_url
