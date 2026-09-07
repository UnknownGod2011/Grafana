#!/usr/bin/env bash
set -euo pipefail

# StageGuard Cloud Run deployment helper.
# This script intentionally does NOT enable remediation and never accepts a
# remediation token/endpoint. Runtime config and Grafana credentials are mounted
# from Secret Manager rather than placed on the command line as secret values.

required=(
  PROJECT_ID
  PROJECT_NUMBER
  REGION
  SERVICE_NAME
  IMAGE_URL
  RUNTIME_SERVICE_ACCOUNT
  IAP_AUDIENCE
  GRAFANA_URL
  TELEMETRY_SECRET
  METRIC_ACTIVATION_SECRET
  LOG_ACTIVATION_SECRET
  GRAFANA_TOKEN_SECRET
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "missing required environment variable: ${name}" >&2
    exit 2
  fi
done

ENABLE_GEMINI="${ENABLE_GEMINI:-false}"
case "${ENABLE_GEMINI,,}" in
  1|true|yes|on) ENABLE_GEMINI=true ;;
  0|false|no|off|'') ENABLE_GEMINI=false ;;
  *) echo "ENABLE_GEMINI must be true or false" >&2; exit 2 ;;
esac

ENV_VARS="STAGEGUARD_TELEMETRY_CONFIG=/config/telemetry.json,STAGEGUARD_METRIC_ACTIVATION=/config/activation.json,STAGEGUARD_LOG_ACTIVATION=/config/log-activation.json,STAGEGUARD_IAP_AUDIENCE=${IAP_AUDIENCE},STAGEGUARD_ENABLE_GEMINI=${ENABLE_GEMINI},GRAFANA_URL=${GRAFANA_URL},GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE=/secrets/grafana-token"
SECRETS="/config/telemetry.json=${TELEMETRY_SECRET}:latest,/config/activation.json=${METRIC_ACTIVATION_SECRET}:latest,/config/log-activation.json=${LOG_ACTIVATION_SECRET}:latest,/secrets/grafana-token=${GRAFANA_TOKEN_SECRET}:latest"

gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URL}" \
  --service-account="${RUNTIME_SERVICE_ACCOUNT}" \
  --no-allow-unauthenticated \
  --iap \
  --set-env-vars="${ENV_VARS}" \
  --set-secrets="${SECRETS}"

gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

echo "StageGuard deployed with IAP enabled and remediation disabled."
echo "Grant roles/iap.httpsResourceAccessor only to intended operators/groups."
