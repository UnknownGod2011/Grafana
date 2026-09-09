# StageGuard on Google Cloud

This guide documents the deployable Google Cloud production boundary for StageGuard. Grafana remains the evidence plane; Cloud Run supplies the API runtime; IAP supplies operator identity; Cloud Logging receives bounded lifecycle audit. Remediation remains a separate write boundary and is disabled by the standard Cloud Run artifact.

## Production image

Build the dedicated API image from the repository root:

```bash
docker build -f Dockerfile.api -t stageguard-api .
```

`Dockerfile.api` is intentionally separate from `runtime/Dockerfile`, which remains the local telemetry simulator image. The API image:

- runs as non-root UID/GID `10001`;
- listens on Cloud Run's `PORT` through `0.0.0.0`;
- includes the official Grafana MCP binary from `grafana/mcp-grafana:1.3.0`;
- launches that MCP binary directly over stdio, so Cloud Run does not require Docker-in-Docker or Docker Compose;
- exposes only `datasource,prometheus,loki` tool categories, with `--disable-write`, `--disable-proxied`, and an eight-line Loki ceiling;
- installs Google production dependencies separately from the standard-library core;
- contains no environment switch that enables production remediation.

Grafana's official MCP documentation supports direct binary/stdio operation and tool-category restriction. The pin should only be advanced after StageGuard's MCP adapter acceptance tests are re-run against the new release.

## Required runtime configuration

The Cloud Run entrypoint refuses startup unless all four bounded production artifacts/identity settings are present:

```text
STAGEGUARD_TELEMETRY_CONFIG=/config/telemetry.json
STAGEGUARD_METRIC_ACTIVATION=/config/activation.json
STAGEGUARD_LOG_ACTIVATION=/config/log-activation.json
STAGEGUARD_IAP_AUDIENCE=<exact signed-header JWT audience>
```

The Grafana MCP child process also needs:

```text
GRAFANA_URL=https://your-grafana.example
GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE=/secrets/grafana-token
```

The token should belong to a least-privilege Grafana service account that can read the configured Prometheus/Loki datasources. Do not reuse remediation credentials.

Optional Gemini advisory briefings remain explicit:

```text
STAGEGUARD_ENABLE_GEMINI=true
GOOGLE_CLOUD_PROJECT=<project-id>
GOOGLE_CLOUD_LOCATION=global
STAGEGUARD_GEMINI_MODEL=gemini-2.5-flash
```

`scripts/deploy_cloud_run.sh` always forwards `GOOGLE_CLOUD_PROJECT=${PROJECT_ID}` because the Vertex adapter requires that value explicitly. `GOOGLE_CLOUD_LOCATION` and `STAGEGUARD_GEMINI_MODEL` are optional operator overrides; the deploy helper defaults them to `global` and `gemini-2.5-flash`, matching the runtime adapter. The helper rejects commas/whitespace in those two values before composing Cloud Run's comma-delimited environment list.

No corresponding `STAGEGUARD_ENABLE_REMEDIATION` variable exists in the standard Cloud Run entrypoint.

## Trust model

For an internet-facing Cloud Run deployment, enable IAP directly on the Cloud Run service and run StageGuard with IAP identity. StageGuard authenticates the signed `X-Goog-IAP-JWT-Assertion` header and derives the operator from the verified JWT `sub` claim. It does **not** trust `X-Goog-Authenticated-User-Id` or `X-Goog-Authenticated-User-Email` as authentication evidence.

Set `STAGEGUARD_IAP_AUDIENCE` to the exact audience emitted by the IAP configuration protecting this service. StageGuard verifies that value independently in addition to signature and issuer checks. Do not accept the audience from request data.

## Durable audit

The Cloud Run artifact fixes `--audit-backend cloud-logging`. `GoogleCloudLoggingAuditSink` writes one bounded structured entry per lifecycle event and rejects credential-, secret-, token-, endpoint-, prompt-, PromQL-, LogQL-, and raw-log-shaped fields. Existing small remediation metadata remains supported for alternate explicitly write-enabled deployments.

StageGuard also constructs a narrow `GoogleCloudAuditReader` in production so restart/reconciliation logic can read the dedicated `stageguard-audit` entries for one incident. The runtime service account therefore needs both the ability to create log entries and to list the StageGuard audit entries it must reconcile. The underlying permissions are `logging.logEntries.create` and `logging.logEntries.list`. Google documents `roles/logging.logWriter` for write access and `roles/logging.viewer` as a predefined role containing ordinary log-entry read access; a custom role can be narrower if your organization requires it. Do not grant private-log access unless StageGuard is intentionally moved to a log class that requires it.

Cloud Logging should use the Cloud Run service account through Application Default Credentials. For stronger retention controls, route the dedicated `stageguard-audit` log to an organization-approved retained/locked destination. StageGuard does not claim ordinary Cloud Logging storage is immutable.

## Deployment helper

`scripts/deploy_cloud_run.sh` deploys the API with direct Cloud Run IAP and no public unauthenticated access. It expects these environment variables:

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
```

The four file values are mounted from Secret Manager to `/config/...` and `/secrets/grafana-token`; secret contents are not placed directly on the command line. `ENABLE_GEMINI=true` is optional. `GOOGLE_CLOUD_LOCATION` and `STAGEGUARD_GEMINI_MODEL` are optional Gemini overrides.

Example invocation after populating those environment variables:

```bash
bash scripts/deploy_cloud_run.sh
```

The helper uses Google's current direct-IAP Cloud Run flow: `gcloud run deploy ... --no-allow-unauthenticated --iap` and then grants `roles/run.invoker` to the project IAP service agent. Operator access (`roles/iap.httpsResourceAccessor`) remains an explicit administrator decision and is not granted automatically by the script.

Before using the helper, grant the runtime service account only the permissions it actually needs:

- `secretmanager.versions.access` on each mounted Secret Manager secret;
- `logging.logEntries.create` for durable lifecycle writes;
- `logging.logEntries.list` for restart-safe lifecycle reconciliation;
- Vertex AI prompt permission only if Gemini is enabled.

The deployment doctor verifies secret access without reading payloads. Logging and Vertex effective-permission checks are the next production-preflight hardening step and should be validated against a disposable project before they become deployment gates.

## Health and readiness

`GET /healthz` is intentionally unauthenticated inside the application and always performs a cheap process-liveness check only:

```json
{"ok":true}
```

`GET /readyz` is also application-unauthenticated so platform health machinery can call it, although IAP/Cloud Run may still protect the route externally. It returns HTTP `200` only when all four bounded production checks are healthy, otherwise HTTP `503`:

```json
{
  "ready": true,
  "checks": {
    "metric_activation": "ok",
    "loki_activation": "ok",
    "prometheus_mcp": "ok",
    "loki_mcp": "ok"
  }
}
```

The readiness probe re-verifies metric and Loki activation freshness on every check, including the exact pinned datasource hashes and semantic contracts. It then performs the official Grafana MCP initialize/tools-list handshake and one read-only `get_datasource` lookup for each pinned datasource UID. This proves the embedded MCP binary can start, required read tools remain available, Grafana credentials/network/org context are usable, and both pinned datasources are actually accessible. It does **not** execute PromQL or LogQL, consume incident evidence, or mutate Grafana.

Readiness responses deliberately expose only `ok`, `failed`, or `missing` check states. MCP/Grafana exception strings, datasource UIDs, Grafana URLs, credentials, PromQL, LogQL, activation hashes, and raw evidence are never returned by `/readyz`.

Cloud Run requires the ingress container to bind to `0.0.0.0` on the injected `PORT`; `runtime/cloudrun_entrypoint.py` enforces that composition while validating `PORT` is in `1..65535`.

## Failure behavior

- Missing telemetry mapping, metric activation, Loki activation, or IAP audience: container startup is refused.
- Invalid `PORT`: container startup is refused.
- Missing IAP assertion: request is rejected.
- Invalid IAP JWT signature, audience, issuer, or subject: request is rejected with a generic authentication error.
- Spoofed unsigned Google identity headers: ignored.
- Missing Google production dependencies: explicit production mode fails rather than silently downgrading.
- Missing Grafana MCP binary: `/readyz` returns `503`; no Docker fallback occurs in Cloud Run.
- Expired or drifted metric/Loki activation: `/readyz` returns `503` even if the process remains live.
- Grafana auth/network/organization failure or inaccessible pinned datasource: `/readyz` returns `503` without exposing the provider error.
- Missing `logging.logEntries.create`: durable audit appends fail.
- Missing `logging.logEntries.list`: restart/reconciliation audit reads fail.
- Missing Gemini project/credentials/Vertex permission: irrelevant unless Gemini was explicitly enabled; with Gemini enabled the advisory layer cannot initialize or call the model until corrected.
- Missing remediation credentials: irrelevant because the standard Cloud Run artifact cannot enable remediation through environment configuration.

## Local validation

On a Docker-capable host:

```bash
docker build -f Dockerfile.api -t stageguard-api .
PORT=8080 docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e STAGEGUARD_TELEMETRY_CONFIG=/config/telemetry.json \
  -e STAGEGUARD_METRIC_ACTIVATION=/config/activation.json \
  -e STAGEGUARD_LOG_ACTIVATION=/config/log-activation.json \
  -e STAGEGUARD_IAP_AUDIENCE='<exact-audience>' \
  stageguard-api
```

A complete local production-path acceptance run also needs mounted config/activation files and a reachable Grafana instance with a read-only service-account token. Do not weaken IAP verification merely to make the production artifact start locally; use the ordinary local bootstrap path for credential-free development.

Once running against a real Grafana evidence plane, verify process and evidence health independently:

```bash
curl -i http://127.0.0.1:8080/healthz
curl -i http://127.0.0.1:8080/readyz
```

`/healthz` should stay `200` as long as the HTTP process is alive. `/readyz` should change to `503` if an activation expires, a datasource UID drifts, the MCP binary becomes unavailable, or Grafana access fails.

## Official references

- Grafana MCP introduction/authentication: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP tools/RBAC reference: https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- Grafana MCP installation/binary: https://grafana.com/docs/grafana/latest/developer-resources/mcp/set-up/install-the-binary/
- Grafana MCP tool restriction/read-only mode: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- Google Cloud Run container contract: https://cloud.google.com/run/docs/container-contract
- Direct IAP for Cloud Run: https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
- IAP signed-header verification: https://cloud.google.com/iap/docs/signed-headers-howto
- IAM Policy Troubleshooter: https://cloud.google.com/policy-intelligence/docs/troubleshoot-access
- Cloud Logging entries.write (`logging.logEntries.create`): https://cloud.google.com/logging/docs/reference/v2/rest/v2/entries/write
- Cloud Logging IAM roles/permissions (`logging.logEntries.list`): https://cloud.google.com/iam/docs/roles-permissions/logging
- Vertex AI generative access control (`aiplatform.endpoints.predict`): https://cloud.google.com/vertex-ai/generative-ai/docs/access-control
