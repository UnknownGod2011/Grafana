# StageGuard on Google Cloud

This guide documents the production identity and audit boundary implemented by StageGuard. It is intentionally separate from Grafana evidence credentials and remediation write credentials.

## Trust model

For an internet-facing Cloud Run deployment, use Google Cloud Identity-Aware Proxy (IAP) and configure StageGuard with `--identity-mode iap`. StageGuard authenticates the signed `X-Goog-IAP-JWT-Assertion` header and derives the operator from the verified JWT `sub` claim. It does **not** trust `X-Goog-Authenticated-User-Id` or `X-Goog-Authenticated-User-Email` as authentication evidence.

Google's current IAP guidance requires validation of the signed JWT because the unsigned convenience headers can be forged if the backend is reached while bypassing IAP. The expected Cloud Run audience has the form:

```text
/projects/PROJECT_NUMBER/locations/REGION/services/SERVICE_NAME
```

Set that exact audience as process configuration:

```bash
export STAGEGUARD_IAP_AUDIENCE='/projects/123456789/locations/us-central1/services/stageguard'
```

The IAP provider lazily imports `google-auth`. Install it only in the production image/runtime that uses IAP:

```bash
pip install google-auth
```

## Durable audit

Use the dedicated Cloud Logging backend:

```bash
pip install google-cloud-logging

python runtime/bootstrap.py \
  --telemetry-config /etc/stageguard/telemetry.json \
  --activation /var/lib/stageguard/activation.json \
  --log-activation /var/lib/stageguard/log-activation.json \
  --host 0.0.0.0 \
  --identity-mode iap \
  --audit-backend cloud-logging \
  --cloud-log-name stageguard-audit
```

`GoogleCloudLoggingAuditSink` writes one bounded structured entry per lifecycle event. It rejects credential-, secret-, token-, endpoint-, prompt-, PromQL-, LogQL-, and raw-log-shaped fields and limits entry size/depth. Existing small remediation metadata remains supported.

Cloud Logging should use the Cloud Run service account through Application Default Credentials. Grant only the minimum logging writer permission required by the deployment. Do not provide remediation credentials to the logging client.

For stronger retention controls, route the dedicated `stageguard-audit` log with a Cloud Logging sink to an organization-approved destination such as a locked/retained logging bucket, Cloud Storage, or BigQuery according to your operational requirements. StageGuard itself does not claim Cloud Logging is immutable; retention/lock policy is a deployment control.

## Cloud Run + IAP checklist

1. Deploy StageGuard to Cloud Run with ingress/auth settings appropriate to the environment.
2. Enable IAP directly on the Cloud Run service where supported by your deployment model.
3. Grant access only to intended operators/groups.
4. Configure `STAGEGUARD_IAP_AUDIENCE` to the exact Signed Header JWT audience.
5. Start StageGuard with `--identity-mode iap`; do not use static bearer auth for the public production path.
6. Start with `--audit-backend cloud-logging` and a dedicated log name.
7. Give the runtime service account only least-privilege access needed for Cloud Logging, Vertex AI if Gemini is enabled, and whatever read-only Grafana MCP access is required.
8. Keep remediation endpoint/token configuration separate and leave `--enable-production-remediation` off until the allowlisted write path has been validated.
9. Keep `/healthz` non-sensitive. All incident/control endpoints remain authenticated inside StageGuard.

## Failure behavior

- Missing IAP assertion: request is rejected.
- Invalid JWT signature, audience, issuer, or subject: request is rejected with a generic authentication error.
- Spoofed unsigned Google identity headers: ignored.
- Missing `google-auth` while IAP mode is selected: startup/runtime refuses the identity path rather than silently falling back.
- Missing `google-cloud-logging` while Cloud Logging audit is selected: startup fails rather than silently downgrading to local JSONL.
- Missing Gemini credentials: irrelevant unless `--enable-gemini` was explicitly selected.
- Missing remediation credentials: irrelevant unless production remediation was explicitly selected.

## Official references

- IAP user identity: https://cloud.google.com/iap/docs/identity-howto
- IAP signed-header verification: https://cloud.google.com/iap/docs/signed-headers-howto
- IAP for Cloud Run: https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
- Cloud Logging Python: https://cloud.google.com/logging/docs/write-query-log-entries-python
- Cloud Logging handlers/client reference: https://cloud.google.com/python/docs/reference/logging/latest
