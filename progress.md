# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable production path now covers:

`strict telemetry mapping → metric/Loki activation pins → official Grafana MCP evidence → deterministic diagnosis + Loki corroboration → authenticated IncidentService → optional revision-bound Gemini briefing → approval-gated remediation → telemetry recovery verification → bounded audit → Cloud Run/IAP deployment → independent liveness/readiness → bounded readiness cache/backoff + StageGuard self-observability`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Production Prometheus and Loki datasource identities and semantic contracts are pinned by expiring activation artifacts.
- Activation freshness and contract/datasource pins are revalidated locally on every readiness request.
- External Grafana MCP readiness probes are bounded and cached so frequent health polling cannot stampede Grafana.
- A previous external success may be reported as `stale` only within a short fixed grace window after a transient refresh failure; once that window expires StageGuard becomes unready.
- A local activation failure is never masked by cached or stale external reachability.
- Gemini remains advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Production writes remain disabled in the standard Cloud Run composition.
- `/healthz` proves process liveness only; `/readyz` proves the bounded evidence plane; `/metrics` exposes fixed, non-sensitive StageGuard readiness telemetry.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP integration with datasource/Prometheus/Loki read tools and writes/proxied tools disabled.
- Deterministic incident investigation and bounded Loki corroboration.
- Strict configurable telemetry mapping, metric preflight, Loki preflight, and expiring activation pins.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport.
- Bounded revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity provider and bounded Google Cloud Logging audit sink.
- Dedicated non-root Cloud Run image with embedded official Grafana MCP binary and remediation disabled.
- `/healthz` liveness + fail-closed `/readyz` using read-only MCP `get_datasource` checks.
- Persistent readiness probe with external-probe TTL, failure backoff, bounded stale-on-transient-failure semantics, single-flight locking, and Prometheus-format self-observability.

## Run log — 2026-09-07 — readiness cache/backoff and self-observability

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected the current repository state, especially:

- `runtime/readiness.py`
- `runtime/api.py`
- `runtime/tests/test_readiness.py`
- `runtime/tests/test_readiness_api.py`
- `README.md`
- `GOOGLE_CLOUD_DEPLOYMENT.md`

The highest-value gap matched the previous handoff: every `/readyz` request constructed a fresh probe and therefore performed two external Grafana MCP datasource lookups, so aggressive platform polling could create avoidable load and concurrent probe stampedes.

### Exact changes made

Updated `runtime/readiness.py`:

- keeps activation verification local and mandatory on every readiness request;
- adds a 15-second external Grafana MCP success TTL by default;
- adds a 5-second retry backoff after external probe failures;
- adds a 30-second maximum age for stale-on-transient-failure behavior;
- returns `stale` only when a previous successful external probe is still inside that bounded grace window;
- makes `stale` readiness-eligible only for external MCP checks; activation checks must still be `ok`;
- serializes readiness evaluation with one lock so concurrent pollers share a single external probe rather than stampeding Grafana;
- classifies external failures only as `connect`, `lookup`, or `unknown`, discarding provider exception strings;
- records only fixed non-sensitive readiness counters and last external probe latency;
- exposes those metrics through `prometheus_metrics()` without datasource IDs, URLs, credentials, activation hashes, queries, or raw evidence;
- validates cache policy at construction time.

Updated `runtime/api.py`:

- creates/reuses one service-owned `EvidencePlaneReadinessProbe` instead of reconstructing the probe per request;
- keeps `/healthz` unchanged and independent from Grafana;
- keeps `/readyz` coarse and fail-closed while allowing bounded `stale` external state when the probe marks it safe;
- adds `GET /metrics` with Prometheus text format for StageGuard readiness self-observability;
- keeps `/metrics` application-unauthenticated for platform scraping and exposes only the bounded fixed metric schema;
- redacts unexpected metrics-generation failures;
- increments the HTTP server version to `StageGuard/0.5`.

Updated `runtime/tests/test_readiness.py`:

- proves repeated polling inside the TTL performs only one Prometheus and one Loki external probe;
- proves activation verification still runs on every request despite cached external results;
- proves a refresh failure becomes `stale` only inside the grace window and becomes `failed` after it expires;
- proves local activation failure immediately makes readiness false even while external reachability is cached healthy;
- proves concurrent polling single-flights the external probes;
- covers bounded failure-class metrics and verifies provider secrets/URLs/datasource UIDs cannot appear in emitted metrics;
- covers invalid cache-policy rejection.

Updated `runtime/tests/test_readiness_api.py`:

- covers HTTP `200` for bounded `stale` external readiness;
- covers `/metrics` Prometheus text behavior without operator authentication;
- covers metrics-error redaction.

### Commits produced this run

- `8faf1153` — bounded readiness caching/backoff and self-observability core
- `62205931` — persistent readiness probe and `/metrics` API surface
- `5c3a92ea` — cache/stale/single-flight/self-metrics regression coverage
- `d7582fa8` — readiness and metrics HTTP contract tests

### Tests / checks / results

No GitHub Actions workflow was created, triggered, rerun, or used as a workaround.

The repository was inspected and modified through the authenticated GitHub connector. This execution environment still does not provide a runnable checkout through normal GitHub DNS, so the Python suite and Docker image were not executed here and are **not claimed as passing**.

No Grafana, Loki, Gemini, IAP, Cloud Logging, Secret Manager, operator, or remediation credential was used. No production Cloud Run or Grafana resource was changed.

### Decisions made

1. **Cache only external reachability, never activation validity.** Expired or drifted activation must fail readiness immediately.
2. **Bound stale readiness by age, not indefinitely.** A transient provider/network failure can reuse a recent success only up to 30 seconds from the last confirmed success.
3. **Single-flight polling per process.** The readiness lock ensures concurrent health requests cannot multiply Grafana MCP calls.
4. **No PromQL/LogQL in readiness.** External checks remain `get_datasource`-based and do not consume incident evidence.
5. **Self-observability stays non-sensitive.** Metric labels are fixed to evidence-plane/failure-class enums and never contain user configuration or provider strings.
6. **`/metrics` is observational only.** It does not run a readiness check or contact Grafana; it exposes the last in-process readiness telemetry.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because a runnable checkout cannot be obtained through normal GitHub DNS.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- Cache/stale behavior has not yet been exercised against a real `mcp-grafana:1.3.0` + Grafana Cloud/self-hosted instance.
- No real Cloud Run + IAP signed assertion has exercised the production API end-to-end.
- Optional Gemini has not yet been exercised against live Vertex AI ADC.
- No operator web console exists yet.

## Single best next step

**Build the first production operator console as a read-mostly incident cockpit: authenticated incident status, deterministic evidence/revision display, bounded Gemini briefing, explicit approval confirmation, and recovery state, while keeping all Grafana/remediation credentials server-side. Add deterministic HTTP/API tests and a minimal static UI that can run behind the existing IAP-protected Cloud Run service without introducing a separate frontend secret boundary.**
