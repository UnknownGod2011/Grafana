# Cloud Run metrics bridge safety

StageGuard keeps its production Cloud Run service authenticated. Prometheus should not require the incident commander to become public just to collect runtime safety metrics, so `runtime/cloud_run_metrics_bridge.py` provides a deliberately narrow authenticated scrape path.

## Trust model

The bridge is an observability adapter, not a general proxy.

It accepts one configured HTTPS StageGuard service origin, obtains a short-lived Google-signed ID token through Application Default Credentials, and performs only `GET /metrics`. Caller headers are never forwarded and the bridge owns the upstream `Authorization` header. The default listener is loopback-only; a non-loopback listener requires explicit opt-in for a trusted private network.

Google's current Cloud Run service-to-service guidance uses an ID token whose audience identifies the receiving Cloud Run service. The Python example uses `google.oauth2.id_token.fetch_id_token` with Application Default Credentials and sends the resulting token as a bearer credential. StageGuard follows that model rather than storing a long-lived service-account key or static bearer token in Prometheus configuration.

Official reference:

- https://cloud.google.com/run/docs/authenticating/service-to-service

## HTTP 200 is not sufficient readiness

A successful HTTP status only proves that *something* answered. It does not prove that the response is a valid StageGuard safety exposition.

This distinction matters for several failure modes:

- a reverse proxy or routing layer can return an HTML/login body with status 200;
- an upstream metrics exporter can fail internally and emit only comments or an empty body;
- a wrong service can be reachable at the configured origin;
- an ambiguous payload can contain more than one copy of a safety-critical sample;
- a malformed or non-finite value can otherwise be accepted as if telemetry were usable.

Therefore `CloudRunMetricsClient.fetch()` validates the response body before either `/readyz` or the bridge `/metrics` endpoint can succeed.

The required identity/integrity sentinel is:

```text
stageguard_remediation_execution_deadline_exceeded <0|1>
```

The bridge requires **exactly one** label-free sentinel sample and requires its value to be finite and exactly `0` or `1`.

The bridge deliberately does not implement a general Prometheus parser. This sentinel is a minimal contract proving that the response is the StageGuard runtime safety exposition expected by the watchdog path. Prometheus remains responsible for parsing the full exposition.

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

## Fail-closed behavior

When ADC, token minting, IAM, network access, upstream HTTP access, response-size limits, or payload validation fail:

- bridge `/readyz` returns sanitized HTTP `503`;
- bridge `/metrics` returns sanitized HTTP `502`;
- `/healthz` remains process-only liveness;
- target URLs, tokens, provider response bodies, ADC exceptions, and IAM details are not returned to callers.

This is important to the watchdog alert model. A transport or payload-integrity failure must become scrape/evidence unavailability, not a fabricated remediation-deadline value.

Prometheus configuration supports treating scrape failures as target failures and exposes target health through its generated `up` series. StageGuard's Grafana runtime-safety rules keep scrape health, telemetry freshness, and positive remediation-deadline evidence as separate signals.

Official Prometheus configuration reference:

- https://prometheus.io/docs/prometheus/latest/configuration/configuration/

## Least privilege

The bridge workload identity should receive only the permission required to invoke the private StageGuard Cloud Run service, normally `roles/run.invoker`. Do not grant broad project roles merely to collect metrics. Do not reuse remediation-provider credentials for observability.

For workloads on Google Cloud, prefer an attached service account. For workloads outside Google Cloud, prefer Workload Identity Federation over downloaded long-lived service-account keys.

## Credential-free regression coverage

`runtime/tests/test_cloud_run_metrics_bridge.py` injects a token supplier and HTTP opener so the safety contract can be tested without Google credentials. Coverage includes:

- HTTPS target/audience restrictions;
- finite positive timeout validation;
- bridge-owned authorization headers;
- loopback-by-default binding;
- process-only `/healthz`;
- authenticated deep `/readyz` semantics;
- rejection of HTML/comment-only/wrong-service HTTP-200 payloads;
- rejection of missing, malformed, duplicate, non-finite, labeled, and non-boolean safety sentinels;
- sanitized failure bodies that do not echo provider/token/target details.

A real disposable-project acceptance is still required before calling the production path fully validated. That rehearsal should prove:

1. private StageGuard Cloud Run service;
2. dedicated invoker service account with only the required invocation permission;
3. ADC ID-token acquisition for the exact service audience;
4. bridge `/readyz` succeeds;
5. bridge `/metrics` returns the StageGuard exposition with the required sentinel;
6. Prometheus reports the bridge target `up == 1`;
7. revoking/removing invocation permission makes `/readyz` fail and Prometheus `up == 0` without exposing credential details;
8. restoring permission recovers scraping without restarting or changing StageGuard lifecycle state.
