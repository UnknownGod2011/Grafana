# Cloud Run metrics bridge safety

StageGuard keeps its production Cloud Run service authenticated. Prometheus should not require the incident commander to become public just to collect runtime safety metrics, so `runtime/cloud_run_metrics_bridge.py` provides a deliberately narrow authenticated scrape path.

## Trust model

The bridge is an observability adapter, not a general proxy. It accepts one configured HTTPS StageGuard service origin, obtains a short-lived Google-signed ID token through Application Default Credentials, and performs only `GET /metrics`. Caller headers are never forwarded and the bridge owns the upstream `Authorization` header.

The default listener is loopback-only. A non-loopback listener requires **both** explicit `--allow-network-bind` opt-in and a configured `--bearer-token` or `STAGEGUARD_BRIDGE_BEARER_TOKEN`; StageGuard refuses to start an anonymously readable non-loopback bridge. `/healthz` remains process-only liveness and does not contact Cloud Run.

Inbound bridge authentication and upstream Cloud Run authentication are intentionally separate credentials. A Prometheus scrape credential is never reused as the Google ID token, and a caller-supplied `Authorization` header is never forwarded upstream.

By default the normalized Google token audience must equal the normalized metrics target origin. A mismatched audience is rejected during client construction, before a token is minted. See `docs/cloud-run-metrics-audience-safety.md` for the explicit escape hatch for intentionally verified deployments.

Official references:

- https://cloud.google.com/run/docs/securing/service-identity
- https://cloud.google.com/run/docs/authenticating/service-to-service
- https://cloud.google.com/docs/authentication/token-types
- https://prometheus.io/docs/prometheus/latest/configuration/configuration/#authorization

## Credential destination and redirects

The configured Cloud Run service origin is the exact destination for the Google bearer credential. The token is installed as an unredirected request header and the production HTTP opener rejects redirects entirely. A routing redirect is treated as observability failure rather than a destination StageGuard should trust automatically.

These controls are complementary:

- audience/target matching prevents silent cross-origin credential delivery before a request starts;
- redirect rejection prevents replay to a different destination after a request starts;
- mandatory bridge bearer authentication prevents anonymous network access whenever the bridge is intentionally bound beyond loopback.

## Inbound scrape authentication

When `STAGEGUARD_BRIDGE_BEARER_TOKEN` is configured, `/readyz` and `/metrics` require an exact `Authorization: Bearer ...` match. Comparison uses `hmac.compare_digest`. Missing or incorrect credentials receive sanitized HTTP `401` with a Bearer challenge and, importantly, do **not** mint an upstream Cloud Run token or contact the upstream service.

For loopback-only bindings this credential remains optional so simple local development can work without extra secret plumbing. For any non-loopback bind, `make_server()` requires both explicit network-bind opt-in and a valid inbound bearer credential before opening the listener.

`/healthz` intentionally remains unauthenticated because it is process-only liveness. It neither fetches StageGuard telemetry nor acquires a Google credential.

For Prometheus, configure the bridge credential using its `authorization` stanza. Treat that credential as a normal scrape secret: source it from the deployment secret mechanism, do not commit it, and rotate it independently of Cloud Run IAM.

## HTTP 200 is not sufficient readiness

A successful HTTP status only proves that *something* answered. It does not prove that the response is a valid StageGuard safety exposition. `CloudRunMetricsClient.fetch()` therefore validates the response before either `/readyz` or bridge `/metrics` can succeed.

The required identity/integrity sentinel is:

```text
stageguard_remediation_execution_deadline_exceeded <0|1>
```

The bridge requires exactly one label-free sentinel sample whose value is finite and exactly `0` or `1`. Labeled sibling series, duplicate samples, non-finite values, HTML/login pages, empty expositions, and malformed samples fail closed.

The bridge deliberately does not implement a general Prometheus parser. The sentinel is the minimum identity/integrity contract needed before forwarding the authenticated response; Prometheus remains responsible for parsing the full exposition.

## Fail-closed behavior

When configuration, bridge authentication, ADC, token minting, IAM, network access, redirects, upstream HTTP access, response-size limits, or payload validation fail:

- an attempted non-loopback bind without an inbound bearer credential is rejected before the listener is created;
- unauthenticated bridge `/readyz` and `/metrics` return sanitized HTTP `401` when inbound auth is configured;
- authenticated bridge `/readyz` returns sanitized HTTP `503` when the upstream path fails;
- authenticated bridge `/metrics` returns sanitized HTTP `502` when the upstream path fails;
- `/healthz` remains process-only liveness;
- target URLs, bridge credentials, Google ID tokens, provider response bodies, ADC exceptions, and IAM details are not returned to callers.

A transport or payload-integrity failure must become scrape/evidence unavailability, not a fabricated remediation-deadline value. Prometheus exposes scrape health through its generated `up` series, while StageGuard's Grafana rules keep scrape health, telemetry freshness, and positive remediation-deadline evidence as separate signals.

## Least privilege

The bridge workload identity should receive only the permission required to invoke the private StageGuard Cloud Run service, normally `roles/run.invoker`. Do not grant broad project roles merely to collect metrics and do not reuse remediation-provider credentials for observability.

For workloads on Google Cloud, prefer an attached user-managed service account. For workloads outside Google Cloud, prefer Workload Identity Federation over downloaded long-lived service-account keys.

## Regression coverage

Focused credential-free tests include:

- `runtime/tests/test_cloud_run_metrics_bridge.py` — target validation, timeout bounds, bridge-owned upstream authorization, liveness/readiness, payload integrity, and sanitized failure responses;
- `runtime/tests/test_cloud_run_metrics_bridge_inbound_auth.py` — inbound bearer validation, fail-closed non-loopback binding, 401 behavior, zero upstream calls for unauthorized requests, Prometheus auth configuration, and acceptance restart credential continuity;
- `runtime/tests/test_cloud_run_metrics_bridge_sentinel_family.py` — sentinel-family ambiguity and labeled-series rejection;
- `runtime/tests/test_cloud_run_metrics_bridge_redirects.py` — redirect isolation requiring the redirect destination to receive zero credentials;
- `runtime/tests/test_cloud_run_metrics_bridge_audience_boundary.py` — same-origin default and reject-before-token-minting mismatch behavior;
- `runtime/tests/test_cloud_run_metrics_acceptance.py` — disposable acceptance-harness behavior without real credentials or Docker side effects.

## Disposable private-Cloud-Run acceptance

`runtime/cloud_run_metrics_acceptance.py` validates an already provisioned private StageGuard Cloud Run service. It is opt-in and not wired into CI.

Prerequisites:

1. A StageGuard Cloud Run service with unauthenticated invocation disabled.
2. Local ADC that can mint an ID token and invoke the service with least-privilege `roles/run.invoker`.
3. A target URL and configured audience that intentionally match.
4. `google-auth` installed.
5. Docker installed and running.
6. StageGuard `/metrics` exposes the canonical deadline sentinel.

Run from the repository root:

```bash
export STAGEGUARD_METRICS_TARGET='https://YOUR-SERVICE-URL'
python runtime/cloud_run_metrics_acceptance.py
```

For each run the harness creates a fresh high-entropy **local bridge bearer credential**. It exists only in memory and in the temporary read-only Prometheus config. The harness never prints it and deletes the temporary config when the acceptance block exits. This local credential is not the Google Cloud Run ID token and cannot be used to invoke Cloud Run.

A passing run proves, in order:

1. anonymous Cloud Run `GET /metrics` receives HTTP `401` or `403`;
2. ADC can mint an ID token for the configured target audience;
3. that identity can invoke private Cloud Run `/metrics`;
4. the returned payload passes StageGuard sentinel validation;
5. the non-loopback local bridge requires its ephemeral bearer credential for `/readyz` and `/metrics`;
6. disposable Prometheus authenticates to that bridge without receiving the Cloud Run ID token;
7. Prometheus observes exactly one `up{job="stageguard-cloud-run-acceptance"} == 1` target;
8. stopping only the local bridge causes exactly `up == 0`;
9. while the bridge is down, the same authenticated production client still validates private Cloud Run `/metrics`;
10. restarting the bridge on the same port with the same ephemeral scrape credential restores exactly `up == 1`.

The harness never creates or changes IAM bindings, deploys or modifies Cloud Run, changes ingress/public access, prints Cloud Run or bridge credentials, calls lifecycle/remediation endpoints, starts GitHub Actions, or intentionally leaves the disposable Prometheus container running.

### Interpreting failures

The command avoids printing credential values, upstream response bodies, ADC exception messages, or provider-error text. Expected failures are summarized by acceptance stage; unexpected exceptions report only the exception class.

A failure is an observability-path failure, not evidence that a remediation deadline was exceeded. Restore the private metrics path and rerun acceptance; do not bypass the bridge by making StageGuard public or weakening the audience/redirect boundaries.
