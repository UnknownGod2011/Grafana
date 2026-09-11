# Cloud Run metrics bridge safety

StageGuard keeps its production Cloud Run service authenticated. Prometheus should not require the incident commander to become public just to collect runtime safety metrics, so `runtime/cloud_run_metrics_bridge.py` provides a deliberately narrow authenticated scrape path.

## Trust model

The bridge is an observability adapter, not a general proxy. It accepts one configured HTTPS StageGuard service origin, obtains a short-lived Google-signed ID token through Application Default Credentials, and performs only `GET /metrics`. Caller headers are never forwarded and the bridge owns the upstream `Authorization` header. The default listener is loopback-only; a non-loopback listener requires explicit opt-in for a trusted private network.

By default the normalized token audience must equal the normalized metrics target origin. A mismatched audience is rejected during client construction, before a token is minted. This prevents a configuration error from silently minting an identity credential intended for one origin and sending it to another. See `docs/cloud-run-metrics-audience-safety.md` for the explicit, narrowly scoped escape hatch for intentionally verified deployments.

Google's current Cloud Run guidance uses an ID token whose audience identifies the receiving service or a configured custom audience. StageGuard follows that model rather than storing a long-lived service-account key or static bearer token in Prometheus configuration.

Official references:

- https://cloud.google.com/run/docs/securing/service-identity
- https://cloud.google.com/run/docs/authenticating/service-to-service
- https://cloud.google.com/run/docs/troubleshooting
- https://cloud.google.com/docs/authentication/token-types

## Credential destination and redirects

The configured service origin is the exact network destination for the bearer credential. The token is installed as an unredirected request header and the production HTTP opener rejects redirects entirely. A routing redirect is treated as observability failure rather than a destination StageGuard should trust automatically.

These two controls are complementary:

- audience/target matching prevents silent cross-origin credential delivery before a request starts;
- redirect rejection prevents a credential from being replayed to a different destination after a request starts.

## HTTP 200 is not sufficient readiness

A successful HTTP status only proves that *something* answered. It does not prove that the response is a valid StageGuard safety exposition. A proxy can return HTML with status 200, an exporter can fail and emit only comments, a wrong service can be reachable, or a payload can contain ambiguous/non-finite safety samples.

Therefore `CloudRunMetricsClient.fetch()` validates the response body before either `/readyz` or bridge `/metrics` can succeed.

The required identity/integrity sentinel is:

```text
stageguard_remediation_execution_deadline_exceeded <0|1>
```

The bridge requires exactly one label-free sentinel sample and requires its value to be finite and exactly `0` or `1`. Any labeled sibling series using that same metric name makes the payload ambiguous and is rejected.

Rejected examples include:

```text
# comment-only response

stageguard_remediation_execution_deadline_exceeded NaN
stageguard_remediation_execution_deadline_exceeded Inf
stageguard_remediation_execution_deadline_exceeded 2
stageguard_remediation_execution_deadline_exceeded{source="spoofed"} 0

# ambiguous duplicate
stageguard_remediation_execution_deadline_exceeded 0
stageguard_remediation_execution_deadline_exceeded 1
```

The bridge deliberately does not implement a general Prometheus parser. The sentinel is the minimum identity/integrity contract needed before forwarding the authenticated response; Prometheus remains responsible for parsing the full exposition.

## Fail-closed behavior

When configuration, ADC, token minting, IAM, network access, redirects, upstream HTTP access, response-size limits, or payload validation fail:

- bridge `/readyz` returns sanitized HTTP `503`;
- bridge `/metrics` returns sanitized HTTP `502`;
- `/healthz` remains process-only liveness;
- target URLs, tokens, provider response bodies, ADC exceptions, and IAM details are not returned to callers.

A transport or payload-integrity failure must become scrape/evidence unavailability, not a fabricated remediation-deadline value. Prometheus exposes scrape health through its generated `up` series, while StageGuard's Grafana rules keep scrape health, telemetry freshness, and positive remediation-deadline evidence as separate signals.

## Least privilege

The bridge workload identity should receive only the permission required to invoke the private StageGuard Cloud Run service, normally `roles/run.invoker`. Do not grant broad project roles merely to collect metrics and do not reuse remediation-provider credentials for observability.

For workloads on Google Cloud, prefer an attached user-managed service account. For workloads outside Google Cloud, prefer Workload Identity Federation over downloaded long-lived service-account keys.

## Credential-free regression coverage

Focused tests include:

- `runtime/tests/test_cloud_run_metrics_bridge.py` — target validation, timeout bounds, bridge-owned authorization, liveness/readiness behavior, payload integrity, and sanitized failure responses;
- `runtime/tests/test_cloud_run_metrics_bridge_sentinel_family.py` — sentinel-family ambiguity and labeled-series rejection;
- `runtime/tests/test_cloud_run_metrics_bridge_redirects.py` — real local redirect isolation requiring the redirect destination to receive zero requests and zero credentials;
- `runtime/tests/test_cloud_run_metrics_bridge_audience_boundary.py` — same-origin default, reject-before-token-minting mismatch behavior, and explicit opt-in semantics;
- `runtime/tests/test_cloud_run_metrics_acceptance.py` — disposable acceptance-harness behavior without real credentials or Docker side effects.

## Disposable-project acceptance harness

`runtime/cloud_run_metrics_acceptance.py` validates an already provisioned private StageGuard Cloud Run service. It is intentionally opt-in and is not wired into CI.

Prerequisites:

1. A StageGuard Cloud Run service with unauthenticated invocation disabled.
2. Local ADC that can mint an ID token and invoke the service using a least-privilege grant, normally service-level `roles/run.invoker`.
3. A target URL and configured Cloud Run audience that intentionally match. For custom-domain deployments, prefer configuring a Cloud Run custom audience matching that domain.
4. `google-auth` installed.
5. Docker installed and running; the harness starts only a disposable Prometheus container.
6. StageGuard `/metrics` exposes the canonical deadline sentinel.

Run from the repository root:

```bash
export STAGEGUARD_METRICS_TARGET='https://YOUR-SERVICE-URL'
python runtime/cloud_run_metrics_acceptance.py
```

The default disposable image is pinned to `prom/prometheus:v3.13.3`. Override it explicitly only when testing another approved Prometheus build:

```bash
STAGEGUARD_ACCEPTANCE_PROMETHEUS_IMAGE='prom/prometheus:YOUR_VERSION' \
  python runtime/cloud_run_metrics_acceptance.py
```

A passing run proves, in order:

1. anonymous `GET /metrics` receives HTTP `401` or `403`;
2. ADC can mint an ID token for the configured target audience;
3. that identity can invoke private Cloud Run `/metrics`;
4. the returned payload passes StageGuard sentinel validation;
5. bridge `/readyz` succeeds using the same authenticated path;
6. bridge `/metrics` forwards only the validated exposition;
7. disposable Prometheus observes exactly one `up{job="stageguard-cloud-run-acceptance"} == 1` target;
8. stopping only the local bridge causes exactly `up == 0`;
9. while the bridge is down, the same authenticated production client still fetches and validates private Cloud Run `/metrics`;
10. restarting the bridge on the same port restores exactly `up == 1`.

The harness never creates or changes IAM bindings, deploys or modifies Cloud Run, changes ingress/public access, prints or persists ID tokens, writes bearer tokens into Prometheus configuration, calls lifecycle/remediation endpoints, starts GitHub Actions, or intentionally leaves the disposable Prometheus container running.

### Interpreting failures

The command avoids printing token values, upstream response bodies, ADC exception messages, or provider-error text. Expected failures are summarized by acceptance stage; unexpected exceptions report only the exception class.

A failure is an observability-path failure, not evidence that a remediation deadline was exceeded. Restore the private metrics path and rerun acceptance; do not bypass the bridge by making StageGuard public or weakening the audience/redirect boundaries.
