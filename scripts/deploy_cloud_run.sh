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
  CHECKPOINT_BUCKET
  CHECKPOINT_HMAC_SECRET
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "missing required environment variable: ${name}" >&2
    exit 2
  fi
done

# Every value below crosses a command-line serialization boundary. In
# particular, --set-env-vars and --set-secrets use comma-delimited mappings.
# Validate their components here even when the deploy doctor was skipped so a
# malformed operator value cannot smuggle an extra environment/secret mapping.
if [[ ! "${PROJECT_NUMBER}" =~ ^[0-9]+$ ]]; then
  echo "PROJECT_NUMBER must contain digits only" >&2
  exit 2
fi
if [[ ! "${RUNTIME_SERVICE_ACCOUNT}" =~ ^[^@[:space:],]+@[^@[:space:],]+\.iam\.gserviceaccount\.com$ ]]; then
  echo "RUNTIME_SERVICE_ACCOUNT must be a service-account email without commas or whitespace" >&2
  exit 2
fi
if [[ ! "${GRAFANA_URL}" =~ ^https?://[^[:space:],]+$ ]]; then
  echo "GRAFANA_URL must be an absolute http(s) URL without commas or whitespace" >&2
  exit 2
fi
if [[ -z "${IAP_AUDIENCE}" || "${IAP_AUDIENCE}" == *","* || "${IAP_AUDIENCE}" =~ [[:space:][:cntrl:]] ]]; then
  echo "IAP_AUDIENCE must be a non-empty value without commas, whitespace, or control characters" >&2
  exit 2
fi
if [[ -z "${IMAGE_URL}" || "${IMAGE_URL}" == *","* || "${IMAGE_URL}" =~ [[:space:][:cntrl:]] ]]; then
  echo "IMAGE_URL must be a non-empty image reference without commas, whitespace, or control characters" >&2
  exit 2
fi
for name in TELEMETRY_SECRET METRIC_ACTIVATION_SECRET LOG_ACTIVATION_SECRET GRAFANA_TOKEN_SECRET CHECKPOINT_HMAC_SECRET; do
  value="${!name}"
  if [[ ! "${value}" =~ ^[A-Za-z0-9_-]{1,255}$ ]]; then
    echo "${name} must be a Secret Manager secret ID (letters, digits, underscores, or hyphens only)" >&2
    exit 2
  fi
done

ENABLE_GEMINI="${ENABLE_GEMINI:-false}"
case "${ENABLE_GEMINI,,}" in
  1|true|yes|on) ENABLE_GEMINI=true ;;
  0|false|no|off|'') ENABLE_GEMINI=false ;;
  *) echo "ENABLE_GEMINI must be true or false" >&2; exit 2 ;;
esac

# GoogleGenAICommanderModel requires GOOGLE_CLOUD_PROJECT explicitly. Cloud Run
# does not guarantee that application-specific variable, so always forward the
# deployment project. Location/model are optional operator overrides with safe
# defaults matching runtime/gemini_commander.py.
GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"
STAGEGUARD_GEMINI_MODEL="${STAGEGUARD_GEMINI_MODEL:-gemini-2.5-flash}"
for name in GOOGLE_CLOUD_LOCATION STAGEGUARD_GEMINI_MODEL; do
  value="${!name}"
  if [[ -z "${value}" || "${value}" == *","* || "${value}" =~ [[:space:]] ]]; then
    echo "${name} must be a non-empty value without commas or whitespace" >&2
    exit 2
  fi
done

# Production Cloud Run deployments always use authenticated durable checkpoint
# state. The HMAC payload itself is never put in this shell command or ENV_VARS;
# Cloud Run resolves it directly from Secret Manager at container start.
if [[ ! "${CHECKPOINT_BUCKET}" =~ ^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$ ]] || \
   [[ "${CHECKPOINT_BUCKET}" == *".."* ]] || \
   [[ "${CHECKPOINT_BUCKET}" == goog* ]] || \
   [[ "${CHECKPOINT_BUCKET}" == *google* ]] || \
   [[ "${CHECKPOINT_BUCKET}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "CHECKPOINT_BUCKET is not a valid bounded GCS bucket name" >&2
  exit 2
fi

CHECKPOINT_OBJECT="${CHECKPOINT_OBJECT:-stageguard/incident-checkpoint.json}"
if [[ -z "${CHECKPOINT_OBJECT}" || \
      "${CHECKPOINT_OBJECT}" == /* || \
      "${CHECKPOINT_OBJECT}" == */ || \
      "${CHECKPOINT_OBJECT}" == *//* || \
      "${CHECKPOINT_OBJECT}" == *","* || \
      "${CHECKPOINT_OBJECT}" == *\\* || \
      "${CHECKPOINT_OBJECT}" =~ ^[[:space:]] || \
      "${CHECKPOINT_OBJECT}" =~ [[:space:]]$ || \
      "${CHECKPOINT_OBJECT}" =~ (^|/)\.\.?(/|$) || \
      "${CHECKPOINT_OBJECT}" =~ [[:cntrl:]] ]]; then
  echo "CHECKPOINT_OBJECT is not a valid bounded object path" >&2
  exit 2
fi
# Runtime and deploy doctor bound object identifiers by UTF-8 bytes, not Unicode
# character count. LC_ALL=C makes Bash expose byte length so multi-byte object
# names cannot pass deployment validation and then fail closed at startup.
CHECKPOINT_OBJECT_BYTES="$(LC_ALL=C; printf '%s' "${CHECKPOINT_OBJECT}" | wc -c)"
CHECKPOINT_OBJECT_BYTES="${CHECKPOINT_OBJECT_BYTES//[[:space:]]/}"
if [[ ! "${CHECKPOINT_OBJECT_BYTES}" =~ ^[0-9]+$ ]] || (( CHECKPOINT_OBJECT_BYTES > 512 )); then
  echo "CHECKPOINT_OBJECT must be at most 512 UTF-8 bytes" >&2
  exit 2
fi

ENV_VARS="STAGEGUARD_TELEMETRY_CONFIG=/config/telemetry.json,STAGEGUARD_METRIC_ACTIVATION=/config/activation.json,STAGEGUARD_LOG_ACTIVATION=/config/log-activation.json,STAGEGUARD_IAP_AUDIENCE=${IAP_AUDIENCE},STAGEGUARD_ENABLE_GEMINI=${ENABLE_GEMINI},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION},STAGEGUARD_GEMINI_MODEL=${STAGEGUARD_GEMINI_MODEL},GRAFANA_URL=${GRAFANA_URL},GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE=/secrets/grafana-token,STAGEGUARD_CHECKPOINT_BUCKET=${CHECKPOINT_BUCKET},STAGEGUARD_CHECKPOINT_OBJECT=${CHECKPOINT_OBJECT}"
SECRETS="/config/telemetry.json=${TELEMETRY_SECRET}:latest,/config/activation.json=${METRIC_ACTIVATION_SECRET}:latest,/config/log-activation.json=${LOG_ACTIVATION_SECRET}:latest,/secrets/grafana-token=${GRAFANA_TOKEN_SECRET}:latest,STAGEGUARD_CHECKPOINT_HMAC_KEY=${CHECKPOINT_HMAC_SECRET}:latest"

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

echo "StageGuard deployed with IAP, authenticated GCS checkpoints, and remediation disabled."
echo "Grant roles/iap.httpsResourceAccessor only to intended operators/groups."