# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable production path now covers:

`strict telemetry mapping → eight-read metric preflight → metric activation pin → one bounded Loki preflight → Loki contract/datasource activation pin → official Grafana MCP Prometheus + Loki adapters → six-read metric diagnosis → mandatory production Loki corroboration → authenticated IncidentService → optional revision-bound Gemini advisory briefing → revision-bound approval → governed allowlisted remediation → credential-isolated HTTPS transport → two-read telemetry recovery verification → bounded local/Cloud Logging audit → direct-IAP Cloud Run API artifact → independent /healthz liveness + fail-closed /readyz evidence readiness`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Production Prometheus and Loki datasource identities and semantic contracts are pinned by expiring activation artifacts.
- Production investigation uses six metric reads first and one bounded Loki corroboration query only after metrics independently diagnose.
- Missing, truncated, or scope-inconsistent Loki evidence forces abstention.
- Gemini is advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Gemini briefing requests must match the exact current incident ID and evidence revision.
- Production Google identity is derived from a verified signed IAP JWT `sub` claim, not unsigned convenience headers or request JSON.
- Approval is tied to the exact evidence revision, single-use, and invalidated by fresh investigation.
- Production writes require a separate explicit process composition; the standard Cloud Run entrypoint has no remediation enable environment switch.
- Action acceptance is never recovery; Grafana telemetry must prove consecutive healthy samples.
- Cloud audit receives only bounded structured lifecycle metadata and rejects secret/query/raw-evidence-shaped fields.
- The Cloud Run image launches the official Grafana MCP binary directly over stdio; it never relies on Docker-in-Docker or Docker Compose.
- `/healthz` proves only HTTP process liveness. `/readyz` independently re-verifies activation freshness/pins and bounded read-only Grafana MCP datasource access before incident traffic should be accepted.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP path with write/proxied tools disabled and only datasource/Prometheus/Loki categories exposed.
- Deterministic four-class incident investigation with exactly six metric reads.
- MCP Prometheus adapter with fail-closed parsing and query provenance.
- Approval-gated remediation with distinct write boundary and telemetry-only recovery proof.
- Strict configurable production telemetry mapping and eight-slot readiness preflight.
- SHA-256 pinned expiring metric activation for non-demo profiles.
- Bounded semantic Loki corroboration using official Grafana MCP `query_loki_logs`.
- Separate Loki activation pinning semantic log contract and actual Loki datasource identity.
- Credential-isolated HTTPS remediation transport and loopback idempotency receiver.
- Bounded Gemini incident-commander layer with strict structured context/output validation.
- Revision-bound authenticated Gemini briefing endpoint with non-sensitive digest auditing.
- Verified Google IAP identity provider using signed JWT assertions and stable subject claims.
- Bounded Google Cloud Logging lifecycle audit sink with explicit production bootstrap selection.
- Dedicated non-root Cloud Run API image with direct official Grafana MCP binary execution.
- Fail-closed Cloud Run entrypoint with fixed IAP + Cloud Logging composition and remediation disabled.
- Safe deployment helper mounting telemetry/activation/Grafana credentials from Secret Manager.
- Production readiness probe that distinguishes liveness from evidence-plane readiness and uses official MCP read-only datasource lookup rather than live incident queries.

## Run log — 2026-09-07 — evidence-plane readiness boundary

### Inspected at start

Read this `progress.md` completely before selecting work. Then inspected current `main`, especially:

- `runtime/api.py`
- `runtime/bootstrap.py`
- `runtime/activation.py`
- `runtime/log_activation.py`
- `runtime/mcp_metric_client.py`
- `runtime/mcp_log_client.py`
- `runtime/mcp_smoke.py`
- `runtime/incident_service.py`
- `runtime/tests/test_api.py`
- `GOOGLE_CLOUD_DEPLOYMENT.md`

The highest-value gap matched the previous handoff: `/healthz` was only process liveness, while orchestration had no way to distinguish a healthy HTTP process from an expired activation, missing embedded MCP binary, inaccessible pinned datasource, or broken Grafana credential/network path.

### Current official research used

Verified current Grafana MCP behavior before choosing the readiness operation:

- Grafana's MCP tools reference documents `get_datasource` as a read-only datasource tool requiring `datasources:read` on the target datasource scope.
- Current official `mcp-grafana` source implements `get_datasource` by UID and marks it read-only/idempotent/non-destructive.
- This makes a UID-scoped `get_datasource` call a better readiness primitive than `tools/list`: it actually reaches Grafana and proves credential/network/organization/datasource access without executing PromQL or LogQL or consuming incident evidence.

References:

- https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- https://github.com/grafana/mcp-grafana/blob/main/tools/datasources.go
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/

### Exact changes made

Added `runtime/readiness.py`:

- introduces `EvidencePlaneReadinessProbe` and bounded `ReadinessResult`;
- re-verifies metric activation freshness, production/profile hash, and pinned Prometheus datasource identity on every readiness check;
- re-verifies Loki activation freshness, semantic log contract hash, and pinned Loki datasource identity on every readiness check;
- calls each existing MCP adapter's `connect()` so initialize/tools-list still prove the required query tool is exposed with `readOnlyHint=true`;
- then performs exactly one read-only official Grafana MCP `get_datasource` lookup for the pinned Prometheus UID and one for the pinned Loki UID;
- does not run PromQL or LogQL and therefore does not create incident evidence or consume investigation query budget;
- catches provider/MCP exceptions and exposes only bounded `ok`/`failed`/`missing` states, never exception strings, datasource UIDs, endpoints, credentials, queries, activation hashes, or raw evidence;
- serializes concurrent readiness checks with a lock so one service process does not race multiple MCP readiness calls through the same clients.

Updated `runtime/api.py`:

- kept `GET /healthz` unchanged as cheap liveness-only `{ "ok": true }`;
- added unauthenticated application-level `GET /readyz` for platform health machinery;
- returns HTTP `200` only when every readiness check is `ok`, otherwise HTTP `503`;
- returns only the four coarse checks: `metric_activation`, `loki_activation`, `prometheus_mcp`, and `loki_mcp`;
- unexpected probe failures are fail-closed and redacted to the same bounded check schema;
- incremented the StageGuard server version string to `0.4`.

Added `runtime/tests/test_readiness.py`:

- covers both fresh activation pins and both bounded datasource lookups;
- proves the lookup is exactly `tools/call → get_datasource → {uid: pinned_uid}`;
- covers expired metric activation;
- covers Loki datasource/contract drift;
- covers missing MCP binary during connect;
- covers Grafana auth/network failure during real datasource lookup;
- covers missing Loki plane;
- asserts provider details such as tokens, private URLs, and secret paths do not appear in the public result.

Added `runtime/tests/test_readiness_api.py`:

- proves `/healthz` does not invoke readiness work;
- proves `/readyz` returns `200` only for a fully ready evidence plane;
- proves `/readyz` returns `503` without requiring API bearer/IAP identity at the application layer;
- proves unexpected readiness exceptions are redacted and fail closed.

Updated `GOOGLE_CLOUD_DEPLOYMENT.md`:

- documents the liveness/readiness split;
- documents the exact readiness response contract;
- documents that readiness uses official MCP `get_datasource` rather than PromQL/LogQL;
- documents expected `503` behavior for expired/drifted activation, missing MCP binary, Grafana auth/network/org failure, or inaccessible pinned datasource;
- adds local `curl /healthz` + `curl /readyz` acceptance guidance.

### Commits produced this run

- `9b3cf48b` — add bounded evidence-plane readiness probe
- `cf756c3e` — expose fail-closed evidence readiness endpoint
- `13fb3673` — test evidence-plane readiness failure modes
- `1570c27a` — test readiness HTTP contract
- `c0b79caa` — verify pinned datasources through Grafana MCP readiness
- `b638e892` — cover bounded Grafana datasource readiness lookup
- `7c209a32` — document Cloud Run evidence readiness contract

### Tests / checks / results

No GitHub Actions workflow was created, triggered, rerun, or used as a workaround.

A direct clean checkout + targeted local test run was attempted with:

```text
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard-run6
cd /tmp/stageguard-run6/runtime
python -m unittest tests.test_readiness tests.test_readiness_api tests.test_api tests.test_cloudrun_entrypoint -v
```

The environment again failed before Python started because DNS resolution for `github.com` is unavailable (`Could not resolve host: github.com`). Therefore the new tests and full Python suite are **not claimed as passing** in this environment.

Repository content and commit state were inspected through the authenticated GitHub connector. No Grafana, Loki, Gemini, IAP, Cloud Logging, Secret Manager, operator, or remediation credential was used. No production Cloud Run or Grafana resource was changed.

### Decisions made

1. **Liveness and readiness stay separate.** `/healthz` must never become expensive or dependent on Grafana.
2. **Readiness re-checks activation expiry continuously.** A container that was ready at startup must become unready when its activation expires.
3. **`tools/list` alone is insufficient.** It proves MCP capability shape but may not prove real Grafana access, so readiness adds a bounded UID-scoped `get_datasource` call.
4. **No readiness PromQL/LogQL.** Platform health checks must not distort telemetry, incident evidence, or query-accounting invariants.
5. **Both evidence planes must be ready.** Production StageGuard is not considered ready with only Prometheus or only Loki.
6. **Provider errors never cross `/readyz`.** Health endpoints disclose only coarse component state.
7. **The official MCP binary remains indispensable.** Readiness itself now depends on real read-only Grafana MCP operations rather than direct Grafana HTTP shortcuts.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because a runnable checkout cannot be obtained via DNS.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- The new `get_datasource` readiness calls have not yet been exercised against a real `mcp-grafana:1.3.0` + Grafana Cloud/self-hosted instance.
- No real Cloud Run + IAP signed assertion has exercised the production API end-to-end.
- No real Secret Manager-mounted telemetry/activation/Grafana token set has exercised the deployment helper.
- Optional Gemini has not yet been exercised against live Vertex AI ADC.
- No operator web console exists yet.

## Single best next step

**Add readiness result caching/backoff with a short bounded TTL and explicit stale semantics, plus runtime metrics for readiness state/latency/failure class that do not expose secrets. Cloud Run and external health systems can poll frequently; without caching, every `/readyz` currently performs two MCP datasource calls. The next increment should keep activation-expiry checks local on every request while rate-limiting external Grafana/MCP probes (for example 10–30 seconds), expose Prometheus-format self-observability for StageGuard itself, and add deterministic tests proving concurrent health polling cannot stampede Grafana or turn a transient single probe failure into unsafe readiness.**
