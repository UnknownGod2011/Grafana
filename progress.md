# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable production path now covers:

`strict telemetry mapping → eight-read metric preflight → metric activation pin → one bounded Loki preflight → Loki contract/datasource activation pin → official Grafana MCP Prometheus + Loki adapters → six-read metric diagnosis → mandatory production Loki corroboration → authenticated IncidentService → optional revision-bound Gemini advisory briefing → revision-bound approval → governed allowlisted remediation → credential-isolated HTTPS transport → two-read telemetry recovery verification → bounded local/Cloud Logging audit → direct-IAP Cloud Run API artifact`

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

## Run log — 2026-09-07 — production Cloud Run packaging

### Inspected at start

Read this `progress.md` completely before selecting work. Then inspected current `main`, especially:

- `runtime/Dockerfile`
- `runtime/bootstrap.py`
- `runtime/api.py`
- `runtime/mcp_metric_client.py`
- `runtime/mcp_smoke.py`
- `runtime/tests/`
- `docker-compose.yml`
- `GOOGLE_CLOUD_DEPLOYMENT.md`

A deployment blocker was found immediately: the current Grafana MCP client default ultimately shells out to `docker compose run ...`. That is appropriate for the local lab but is not a valid production Cloud Run dependency. The Cloud Run artifact therefore needed the official MCP binary inside the API container and an explicit direct-stdio command.

### Current official research used

Verified current official sources before packaging:

- Grafana documents installing and running `mcp-grafana` directly as a binary over stdio.
- Grafana documents `--enabled-tools`, `--disable-write`, `--disable-proxied`, and Loki result ceilings as supported hardening controls.
- The latest official `grafana/mcp-grafana` GitHub release visible on 2026-09-07 is `v1.3.0` (published 2026-08-28).
- Google Cloud Run requires the ingress container to bind to `0.0.0.0` on the injected `PORT`.
- Google currently recommends direct IAP integration on Cloud Run; the CLI path is `gcloud run deploy ... --no-allow-unauthenticated --iap`, followed by `roles/run.invoker` for the IAP service agent.

References:

- https://grafana.com/docs/grafana/latest/developer-resources/mcp/set-up/install-the-binary/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- https://github.com/grafana/mcp-grafana/releases/tag/v1.3.0
- https://cloud.google.com/run/docs/container-contract
- https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run

### Exact changes made

Added `runtime/cloudrun_entrypoint.py`:

- converts Cloud Run process configuration into a fixed StageGuard bootstrap invocation;
- requires telemetry mapping, metric activation, Loki activation, and exact IAP audience before startup;
- validates `PORT` is an integer in `1..65535`;
- fixes `--identity-mode iap`, `--audit-backend cloud-logging`, and `--host 0.0.0.0`;
- keeps Gemini optional through `STAGEGUARD_ENABLE_GEMINI`;
- intentionally exposes no environment switch for `--enable-production-remediation`.

Added `runtime/requirements-cloudrun.txt`:

- isolates `google-auth`, `google-cloud-logging`, and `google-genai` production dependencies from the standard-library local core.

Added root `Dockerfile.api`:

- uses a dedicated production API image rather than repurposing the simulator Dockerfile;
- imports the official `mcp-grafana` binary from `grafana/mcp-grafana:1.3.0`;
- runs StageGuard as non-root UID/GID `10001`;
- installs CA certificates for outbound HTTPS and only the Google production Python dependencies;
- sets the Cloud Run port default to `8080` while the entrypoint still honors injected `PORT`;
- configures the embedded MCP command as direct stdio with `--disable-write`, `--disable-proxied`, `--enabled-tools datasource,prometheus,loki`, and `--max-loki-log-limit 8`;
- therefore removes Docker/Docker Compose as a runtime requirement for production evidence reads.

Added `runtime/tests/test_cloudrun_entrypoint.py`:

- covers fixed IAP + Cloud Logging composition;
- proves remediation cannot be enabled through the production entrypoint;
- covers Gemini opt-in behavior;
- covers missing config/IAP values failing closed;
- covers invalid/out-of-range `PORT` rejection.

Added `scripts/deploy_cloud_run.sh`:

- requires project/service/image/runtime-service-account/IAP/Grafana/config-secret identifiers;
- deploys with `--no-allow-unauthenticated --iap`;
- mounts telemetry mapping, metric activation, Loki activation, and Grafana token from Secret Manager file paths;
- grants `roles/run.invoker` to the IAP service agent;
- does not grant operator IAP access automatically;
- contains no remediation endpoint/token handling.

Updated `docker-compose.yml`:

- advanced the official MCP pin from `1.1.0` to current `1.3.0`;
- corrected the bounded read categories to include Loki explicitly (`datasource,prometheus,loki`);
- added `--max-loki-log-limit 8` while retaining write/proxied-tool disablement.

Updated `GOOGLE_CLOUD_DEPLOYMENT.md`:

- documents the actual API image and direct-binary MCP architecture;
- documents all required environment/file mounts and Secret Manager boundaries;
- documents the deployment helper and current direct-IAP Cloud Run flow;
- documents health semantics, failure behavior, and local image validation;
- clarifies that standard Cloud Run deployment cannot enable remediation via environment configuration.

### Commits produced this run

- `c4ee5446` — fail-closed Cloud Run API entrypoint
- `acd6f905` — Cloud Run Google dependencies
- `18c8c31e` — production API image
- `981433bf` — Cloud Run entrypoint tests
- `e870c4ad` — pin API image to current Grafana MCP release
- `30aead51` — update local MCP pin/read categories
- `59069eee` — safe Cloud Run deployment helper
- `03028348` — document deployable Cloud Run artifact

### Tests / checks / results

No GitHub Actions workflow was created, triggered, or rerun.

A direct clean checkout + targeted test run was attempted with:

```text
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git ...
python -m unittest tests.test_cloudrun_entrypoint -v
```

The environment failed before Python started because DNS resolution for `github.com` is still unavailable (`Could not resolve host: github.com`). Therefore the new test and full Python suite are **not claimed as passing** in this environment.

Repository state, official release metadata, and all changed files were inspected through the authenticated GitHub connector. No Grafana, Loki, Gemini, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials were used. No production resource was deployed.

### Decisions made

1. **No Docker-in-Docker in Cloud Run.** The official Grafana MCP binary is embedded and launched directly over stdio.
2. **MCP stays indispensable but tightly bounded.** Only datasource, Prometheus, and Loki categories are available; writes and proxied tools are disabled.
3. **Pin to current official MCP release (`1.3.0`).** Version movement remains deliberate and should be acceptance-tested before future upgrades.
4. **Production image is separate from the simulator image.** Local telemetry development stays lightweight and unchanged.
5. **Cloud Run composition fails closed.** Missing evidence activations, telemetry mapping, IAP audience, or invalid `PORT` prevents startup.
6. **Remediation cannot be accidentally enabled by an environment variable.** A write-enabled deployment must use an intentionally different command/composition.
7. **Secrets/config are mounted as files.** The deployment helper does not place Grafana token contents directly on the CLI.
8. **Direct Cloud Run IAP is now the documented default.** No load balancer is required solely to obtain IAP protection on current Cloud Run.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because a runnable checkout cannot be obtained via DNS.
- `Dockerfile.api` has not yet been built on a Docker-capable host, so the cross-stage `/app/mcp-grafana` copy from `grafana/mcp-grafana:1.3.0` still needs real image-build acceptance.
- No real Cloud Run + IAP signed assertion has exercised `GoogleIapIdentityProvider` end-to-end.
- No real Secret Manager-mounted telemetry/activation/Grafana token set has exercised the deploy helper.
- No live Grafana Cloud/self-hosted production instance has yet proven metric + Loki reads through the embedded `mcp-grafana:1.3.0` binary.
- Optional Gemini has not yet been exercised against live Vertex AI ADC.
- No operator web console exists yet.

## Single best next step

**Add a production readiness endpoint/state that distinguishes process liveness from evidence-plane readiness, then add startup/readiness acceptance around the embedded `mcp-grafana:1.3.0` binary: verify both pinned datasource identities, activation freshness, and one bounded read-only MCP capability handshake before reporting ready. Keep `/healthz` cheap/liveness-only, add `/readyz` with no raw evidence or secret leakage, and test failure modes for missing MCP binary, Grafana auth failure, datasource drift, and expired activations. This is the highest-value next increment because the Cloud Run artifact now exists, but orchestration still needs a reliable signal that it is safe to receive incident traffic.**
