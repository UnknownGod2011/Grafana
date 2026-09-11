# Cloud Run metrics bridge safety

StageGuard keeps its production Cloud Run service authenticated. Prometheus should not require the incident commander to become public just to collect runtime safety metrics, so `runtime/cloud_run_metrics_bridge.py` provides a deliberately narrow authenticated scrape path.

## Trust model

The bridge is an observability adapter, not a general proxy.

It accepts one configured HTTPS StageGuard service origin, obtains a short-lived Google-signed ID token through Application Default Credentials, and performs only `GET /metrics`. Caller headers are never forwarded and the bridge owns the upstream `Authorization` header. The default listener is loopback-only; a non-loopback listener requires explicit opt-in for a trusted private network.

Google's current Cloud Run service-to-service guidance uses an ID token whose audience identifies the receiving Cloud Run service. The Python example uses `google.oauth2.id_token.fetch_id_token` with Application Default Credentials and sends the resulting token as a bearer credential. StageGuard follows that model rather than storing a long-lived service-account key or static bearer token in Prometheus configuration.

Official references:

- https://cloud.google.com/run/docs/authenticating/service-to-service
- https://cloud.google.com/docs/authentication/get-id-token

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

Official Prometheus references:

- https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- https://prometheus.io/docs/prometheus/latest/querying/api/

## Least privilege

The bridge workload identity should receive only the permission required to invoke the private StageGuard Cloud Run service, normally `roles/run.invoker`. Do not grant broad project roles merely to collect metrics. Do not reuse remediation-provider credentials for observability.

For workloads on Google Cloud, prefer an attached service account. For workloads outside Google Cloud, prefer Workload Identity Federation over downloaded long-lived service-account keys.

## Credential-free regression coverage

`runtime/tests/test_cloud_run_metrics_bridge.py` injects a token supplier and HTTP opener so the bridge safety contract can be tested without Google credentials. Coverage includes:

- HTTPS target/audience restrictions;
- finite positive timeout validation;
- bridge-owned authorization headers;
- loopback-by-default binding;
- process-only `/healthz`;
- authenticated deep `/readyz` semantics;
- rejection of HTML/comment-only/wrong-service HTTP-200 payloads;
- rejection of missing, malformed, duplicate, non-finite, labeled, and non-boolean safety sentinels;
- sanitized failure bodies that do not echo provider/token/target details.

`runtime/tests/test_cloud_run_metrics_acceptance.py` covers the disposable acceptance harness without credentials or Docker side effects. It verifies the anonymous-access negative contract, exact binary Prometheus `up` interpretation, ambiguity/non-finite rejection, ephemeral/read-only container flags, CLI error sanitization, and the ordered local `up: 1 -> 0 -> 1` bridge failure/recovery contract. It also proves the authoritative upstream is rechecked only after Prometheus has observed the local bridge down.

## Disposable-project acceptance harness

`runtime/cloud_run_metrics_acceptance.py` validates an **already provisioned** private StageGuard Cloud Run service. It is intentionally opt-in and is not wired into CI.

Prerequisites:

1. A StageGuard Cloud Run service deployed with unauthenticated invocation disabled.
2. The identity represented by local ADC can mint an ID token and has the minimum Cloud Run invocation permission required for that service. `roles/run.invoker` is the normal service-level grant.
3. `google-auth` is installed as required by the runtime bridge.
4. Docker is installed and the daemon is running. The harness starts only a disposable Prometheus container.
5. The StageGuard `/metrics` endpoint exposes the canonical deadline sentinel described above.

Run from the repository root:

```bash
export STAGEGUARD_METRICS_TARGET='https://YOUR-SERVICE-URL'
python runtime/cloud_run_metrics_acceptance.py
```

If the ID-token audience differs from the service origin, set it explicitly:

```bash
export STAGEGUARD_METRICS_AUDIENCE='https://EXPECTED-AUDIENCE'
python runtime/cloud_run_metrics_acceptance.py
```

The default disposable image is pinned to `prom/prometheus:v3.13.3`. Override it explicitly when testing another approved Prometheus build:

```bash
STAGEGUARD_ACCEPTANCE_PROMETHEUS_IMAGE='prom/prometheus:YOUR_VERSION' \
  python runtime/cloud_run_metrics_acceptance.py
```

A passing run proves, in order:

1. an anonymous/no-token `GET /metrics` receives HTTP `401` or `403`;
2. ADC can mint an ID token for the configured audience;
3. that identity can invoke private Cloud Run `/metrics`;
4. the returned payload passes StageGuard's sentinel identity/integrity check;
5. bridge `/readyz` succeeds using the same authenticated path;
6. bridge `/metrics` forwards only a validated StageGuard exposition;
7. disposable Prometheus scrapes the bridge and returns exactly one `up{job="stageguard-cloud-run-acceptance"} == 1` target;
8. the harness stops **only** the local bridge and Prometheus observes the same target as exactly `up == 0`;
9. while that local bridge is down, the same authenticated production client successfully fetches and validates private Cloud Run `/metrics`, proving the upstream service/IAM path remained intact;
10. the bridge is restarted on the exact same port and Prometheus observes the target recover to exactly `up == 1`.

The anonymous check is deliberately used instead of temporarily revoking IAM. The harness therefore does not mutate service IAM, cannot accidentally remove production access, and remains safe to use against a disposable/private test deployment.

The failure/recovery phase is similarly constrained. It does **not** stop, redeploy, reconfigure, or change IAM on Cloud Run. Only the local bridge process is stopped. Because Prometheus keeps scraping the same fixed target, the bridge must recover on the same local port; a different target cannot accidentally satisfy the recovery check.

### What the harness does not do

It never:

- creates or changes IAM bindings;
- deploys or modifies Cloud Run services;
- changes ingress or public-access settings;
- stops or restarts Cloud Run;
- prints or persists ID tokens;
- writes a bearer token into Prometheus configuration;
- calls incident, approval, execution, recovery, or remediation endpoints;
- starts GitHub Actions;
- leaves the disposable Prometheus container running after normal completion.

The bridge binds to `0.0.0.0` only for the duration of the acceptance so the isolated Docker container can reach it through Docker's `host.docker.internal` host-gateway mapping. Prometheus's published API port is bound to `127.0.0.1` only, and its generated configuration is mounted read-only. The bridge and container are torn down in `finally` cleanup.

### Interpreting failures

The command intentionally avoids printing token values, upstream response bodies, ADC exception messages, or provider-error text. Expected operator-facing failures are summarized by acceptance stage. Unexpected exceptions report only the exception class.

A failure should be treated as an observability-path failure, not evidence that a remediation deadline was exceeded. Restore the private metrics path and rerun acceptance; do not bypass the bridge by making StageGuard public.
