# StageGuard on Google Cloud

This guide documents the deployable Google Cloud production boundary for StageGuard. Grafana remains the evidence plane; Cloud Run supplies the API runtime; IAP supplies operator identity; Cloud Logging receives bounded lifecycle audit; Cloud Storage holds an authenticated restart-durable incident checkpoint. Remediation remains a separate write boundary and is disabled by the standard Cloud Run artifact.

## Production image

Build the dedicated API image from the repository root:

```bash
docker build -f Dockerfile.api -t stageguard-api .
```

`Dockerfile.api` is intentionally separate from `runtime/Dockerfile`, which remains the local telemetry simulator image. The API image runs as non-root UID/GID `10001`, listens on Cloud Run's `PORT` through `0.0.0.0`, embeds the official Grafana MCP binary from `grafana/mcp-grafana:1.4.1`, launches it directly over stdio, restricts it to `datasource,prometheus,loki` with writes/proxying disabled, and contains no environment switch that enables production remediation.

## Required runtime configuration

The Cloud Run entrypoint requires the bounded production configuration and exact IAP audience:

```text
STAGEGUARD_TELEMETRY_CONFIG=/config/telemetry.json
STAGEGUARD_METRIC_ACTIVATION=/config/activation.json
STAGEGUARD_LOG_ACTIVATION=/config/log-activation.json
STAGEGUARD_IAP_AUDIENCE=<exact signed-header JWT audience>
GRAFANA_URL=https://your-grafana.example
GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE=/secrets/grafana-token
```

The Grafana token should belong to a least-privilege service account that can read only the configured Prometheus/Loki datasources. Do not reuse remediation credentials.

Standard production deployment also requires authenticated GCS checkpointing:

```text
STAGEGUARD_CHECKPOINT_BUCKET=<existing GCS bucket>
STAGEGUARD_CHECKPOINT_OBJECT=stageguard/incident-checkpoint.json
STAGEGUARD_CHECKPOINT_HMAC_KEY=<Secret Manager supplied key, 32-512 UTF-8 bytes>
```

The object is a single bounded checkpoint updated with generation preconditions. It is signed with HMAC before storage and verified before restore, so storage write permission alone cannot forge trusted StageGuard state. `STAGEGUARD_CHECKPOINT_HMAC_KEY` is injected through Cloud Run Secret Manager integration and must not be placed in ordinary environment configuration, shell history, or repository files. The Cloud Run entrypoint rejects keys shorter than 32 bytes, larger than 512 bytes, or containing leading/trailing whitespace or control characters; generate a random secret rather than a human-readable phrase.

Optional Gemini advisory briefings remain explicit:

```text
STAGEGUARD_ENABLE_GEMINI=true
GOOGLE_CLOUD_PROJECT=<project-id>
GOOGLE_CLOUD_LOCATION=global
STAGEGUARD_GEMINI_MODEL=gemini-2.5-flash
```

The remediation/recovery execution watchdog defaults to 60 seconds and may only be configured inside the fixed production safety range of 1 through 600 seconds:

```text
STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS=60
```

Values outside that range, non-finite numbers, blanks, and malformed numbers refuse startup instead of silently weakening the watchdog.

`scripts/deploy_cloud_run.sh` always forwards `GOOGLE_CLOUD_PROJECT=${PROJECT_ID}`. Location/model default to `global` and `gemini-2.5-flash`. No corresponding `STAGEGUARD_ENABLE_REMEDIATION` variable exists in the standard production entrypoint.

## Trust model

Enable IAP directly on the Cloud Run service. StageGuard verifies the signed `X-Goog-IAP-JWT-Assertion`, including signature, issuer, audience, and subject, and derives the operator from the verified `sub`. It does not trust unsigned Google identity headers as authentication evidence.

Set `STAGEGUARD_IAP_AUDIENCE` to the exact audience emitted by the IAP configuration protecting this service. Do not accept the audience from request data.

## Durable audit

The Cloud Run artifact fixes `--audit-backend cloud-logging`. `GoogleCloudLoggingAuditSink` writes bounded structured lifecycle events and rejects secret-, token-, prompt-, query-, endpoint-, and raw-log-shaped fields. `GoogleCloudAuditReader` reads the StageGuard audit stream for restart/reconciliation.

The runtime service account therefore needs:

- `logging.logEntries.create` for durable audit writes;
- `logging.logEntries.list` for restart/reconciliation reads.

StageGuard does not claim ordinary Cloud Logging storage is immutable. For stronger retention guarantees, route the dedicated StageGuard audit log to an organization-approved retained/locked destination.

## Durable checkpoint IAM

`GoogleCloudStorageCheckpointStore` uses exactly one configured object. Its runtime operations are:

1. check/read object metadata and data;
2. create the object when no checkpoint exists;
3. overwrite the same object with `if_generation_match` optimistic concurrency.

Therefore the Cloud Run runtime service account needs exactly these Cloud Storage object permissions on the checkpoint bucket/object scope:

```text
storage.objects.get
storage.objects.create
storage.objects.delete
```

`storage.objects.delete` is required because Cloud Storage treats replacement of an existing object as an overwrite. StageGuard runtime does **not** require `storage.objects.list`, `storage.buckets.list`, bucket creation/deletion, or bucket IAM administration. `roles/storage.objectUser` on the dedicated checkpoint bucket is the standard predefined role that supplies the object read/create/delete capability; a narrower custom/inherited grant is also acceptable if it preserves the exact permissions above.

The deployment doctor evaluates these permissions through IAM Policy Troubleshooter against the exact object full resource name:

```text
//storage.googleapis.com/projects/_/buckets/<bucket>/objects/<object>
```

The underscore in the Cloud Storage project position is required by Google's full-resource-name format. The doctor does not download the checkpoint payload, write an object, mutate IAM, or create a bucket.

The operator running the doctor needs enough visibility to describe the configured bucket. This metadata visibility is a preflight/operator concern and is not a StageGuard runtime permission.

## Deployment helper

`scripts/deploy_cloud_run.sh` expects:

```text
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
```

Optional:

```text
CHECKPOINT_OBJECT=stageguard/incident-checkpoint.json
ENABLE_GEMINI=false
GOOGLE_CLOUD_LOCATION=global
STAGEGUARD_GEMINI_MODEL=gemini-2.5-flash
STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS=60
```

The telemetry/activation files, Grafana token, and checkpoint HMAC key are resolved from Secret Manager. Secret payloads are never placed directly in the command's ordinary environment-variable list.

Before deployment run the credential-safe doctor:

```bash
python scripts/gcp_deploy_doctor.py --offline --json
python scripts/gcp_deploy_doctor.py --json
```

`--offline` validates syntax and required deployment inputs but can never report `ready_to_deploy=true`. Live mode additionally verifies project access, required APIs, service-account existence, Secret Manager resources and effective secret access, Cloud Logging permissions, checkpoint-bucket metadata visibility, exact Cloud Storage object permissions, conditional Vertex prediction access, and Artifact Registry image availability.

Only after `ready_to_deploy` is true:

```bash
bash scripts/deploy_cloud_run.sh
```

The helper uses direct Cloud Run IAP with `--no-allow-unauthenticated --iap`, then grants `roles/run.invoker` to the project IAP service agent. Operator access (`roles/iap.httpsResourceAccessor`) remains an administrator decision and is not granted automatically.

## Least-privilege runtime permission summary

Before using the helper, grant the runtime service account only what the configured features need:

- `secretmanager.versions.access` on each mounted secret, including the checkpoint HMAC secret;
- `logging.logEntries.create`;
- `logging.logEntries.list`;
- `storage.objects.get` on the checkpoint scope;
- `storage.objects.create` on the checkpoint scope;
- `storage.objects.delete` on the checkpoint scope;
- `aiplatform.endpoints.predict` on the configured Gemini publisher model only when Gemini is enabled.

The doctor verifies effective permissions rather than assuming role names. Denied, unknown, malformed, or unavailable Policy Troubleshooter results fail closed.

## Health and readiness

`GET /healthz` is an unauthenticated process-liveness check inside the application and returns `{"ok":true}` while the HTTP process is alive.

`GET /readyz` returns HTTP `200` only when bounded production trust is healthy. It re-verifies metric/Loki activation freshness before touching external Grafana MCP, then performs the official MCP initialize/tools-list handshake and one read-only `get_datasource` lookup for each pinned datasource. It does not execute incident PromQL/LogQL or mutate Grafana. When local activation/pin trust is invalid, Grafana MCP probes are not started at all.

Readiness responses expose only bounded `ok`, `failed`, `missing`, or `blocked` states and do not return Grafana URLs, datasource UIDs, credentials, raw provider exceptions, PromQL, LogQL, activation hashes, or evidence.

## Failure behavior

- Missing telemetry mapping, activation files, IAP audience, or required durable checkpoint inputs: startup/deployment is refused.
- Invalid checkpoint bucket/object identifiers, checkpoint HMAC keys outside 32-512 UTF-8 bytes, or checkpoint HMAC keys with boundary whitespace/control characters: startup is refused.
- Remediation execution watchdog values below 1 second, above 600 seconds, non-finite, blank, or malformed: startup is refused.
- Missing checkpoint HMAC Secret Manager access: deployment doctor fails closed.
- Missing `storage.objects.get`: restart checkpoint reads cannot be trusted and deployment doctor fails closed.
- Missing `storage.objects.create`: first checkpoint creation cannot succeed and deployment doctor fails closed.
- Missing `storage.objects.delete`: replacement of an existing checkpoint cannot succeed and deployment doctor fails closed.
- Checkpoint generation conflict: StageGuard surfaces a bounded concurrency conflict instead of silently overwriting another writer.
- Missing IAP assertion or invalid IAP JWT signature/audience/issuer/subject: request is rejected.
- Missing Grafana MCP binary, expired activation, inaccessible pinned datasource, or Grafana auth/network failure: `/readyz` returns `503` without exposing provider details.
- Missing `logging.logEntries.create` or `logging.logEntries.list`: deployment doctor fails closed and the relevant durable audit operation would fail.
- Missing Vertex project/credentials/prediction permission: irrelevant unless Gemini is explicitly enabled; with Gemini enabled the advisory layer cannot initialize/call the model.
- Missing remediation credentials: irrelevant because standard Cloud Run deployment cannot enable remediation via environment configuration.

## Local validation

For credential-free development use the ordinary local bootstrap path rather than weakening production IAP/checkpoint requirements. A complete production-path acceptance test needs mounted config/activation files, a reachable read-only Grafana instance, an authorized GCP project, and the required checkpoint bucket/secrets.

Once running, verify liveness and evidence readiness independently:

```bash
curl -i http://127.0.0.1:8080/healthz
curl -i http://127.0.0.1:8080/readyz
```

## Official references

- Grafana MCP introduction/authentication: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP tools/RBAC reference: https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- Grafana MCP installation/binary: https://grafana.com/docs/grafana/latest/developer-resources/mcp/set-up/install-the-binary/
- Grafana MCP tool restriction/read-only mode: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- Google Cloud Run container contract: https://cloud.google.com/run/docs/container-contract
- Direct IAP for Cloud Run: https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
- IAP signed-header verification: https://cloud.google.com/iap/docs/signed-headers-howto
- IAM Policy Troubleshooter: https://cloud.google.com/policy-intelligence/docs/troubleshoot-access
- Cloud Storage object permissions: https://cloud.google.com/storage/docs/access-control/iam-permissions
- Cloud Storage upload overwrite permissions: https://cloud.google.com/storage/docs/uploading-objects-from-memory
- Cloud Storage object download permission: https://cloud.google.com/storage/docs/downloading-objects
- Google Cloud full resource names: https://cloud.google.com/iam/docs/full-resource-names
- Cloud Logging entries.write: https://cloud.google.com/logging/docs/reference/v2/rest/v2/entries/write
- Cloud Logging IAM roles/permissions: https://cloud.google.com/iam/docs/roles-permissions/logging
- Vertex AI generative access control: https://cloud.google.com/vertex-ai/generative-ai/docs/access-control
