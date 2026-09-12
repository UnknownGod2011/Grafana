# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, and explicit no-replay reconciliation for post-remediation persistence uncertainty.

Core invariants retained:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Durable checkpoint/audit failures fail closed and uncommitted state is not operator-visible lifecycle authority.
- Once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Simultaneous execution uncertainty and audit-integrity failure remains externally visible as a bounded no-replay safety state.
- Browser/API surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- Runtime metric readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.
- A metrics bridge bound beyond loopback should authenticate inbound `/readyz` and `/metrics` independently from the upstream Cloud Run ID token.

## Recent hardening retained

- `ExecutionSafeIncidentService` prioritizes execution uncertainty once provider dispatch may have occurred.
- Authenticated lifecycle responses expose bounded composite safety state and, only when appropriate, strict `sg-<40 lowercase hex>` reconciliation references.
- `/readyz`, Prometheus, and the operator console consistently expose no-replay state without exporting high-cardinality reconciliation identifiers through metrics.
- `execution_uncertain_audit_failed` renders `DO NOT REPLAY REMEDIATION` and disables lifecycle mutation controls.
- Base and anchored checkpoint-backed transition failures restore the last committed snapshot and keep append-before-persistence residue out of committed operator history.
- Authenticated evidence-unavailable briefing/approval/execution bypass attempts fail closed with no Gemini or remediation side effects.
- The Cloud Run metrics bridge rejects ID-token-bearing redirects, validates target/audience boundaries, validates an unambiguous StageGuard sentinel, and now supports separate inbound bearer authentication for `/readyz` and `/metrics`.
- The disposable private-Cloud-Run acceptance harness now generates one fresh local scrape credential per run so its required `0.0.0.0` Docker-reachable bridge is not anonymously readable.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Baseline incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

## Prior 2026-09-12 safety work retained

- Added composite lifecycle safety states and bounded reconciliation references.
- Aligned the dedicated remediation-uncertainty Prometheus gauge with all non-clear reconciliation barriers.
- Added operator `DO NOT REPLAY` interlocks and real-browser acceptance coverage for post-provider persistence uncertainty.
- Added base/anchored snapshot-authority regressions so failed persistence cannot publish uncommitted investigation, approval, or outcome state.
- Added evidence-unavailable lifecycle and authenticated bypass regressions.
- Added Cloud Run metrics audience, redirect, sentinel-family, bridge, and disposable `up: 1 -> 0 -> 1` acceptance scaffolding.

## Run log — 2026-09-12 — authenticated non-loopback metrics bridge

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the repository tree and the current implementations/tests for:
- `runtime/cloud_run_metrics_bridge.py`;
- `runtime/cloud_run_metrics_acceptance.py`;
- `runtime/tests/test_cloud_run_metrics_bridge.py`;
- `runtime/tests/test_cloud_run_metrics_acceptance.py`;
- `docs/cloud-run-metrics-bridge-safety.md`;
- the existing audience, redirect, sentinel-family, and private-Cloud-Run acceptance structure.

A local checkout was attempted first but the execution environment again failed to resolve `github.com`. Direct authenticated GitHub repository access remained available, so inspection and writes were performed only in `UnknownGod2011/Grafana` through the repository connector. No unrelated repository was touched.

### Finding

The private Cloud Run acceptance harness deliberately starts its local metrics bridge on `0.0.0.0` so disposable Prometheus inside Docker can reach the host through `host.docker.internal`. The upstream Cloud Run request is strongly authenticated, but the local bridge itself previously allowed anonymous access to `/readyz` and `/metrics` once a non-loopback bind was explicitly enabled.

That meant a local-network/process peer able to reach the acceptance host could read validated StageGuard runtime metrics from the bridge. The peer could not obtain the Cloud Run ID token, but the scrape surface was still wider than necessary. The acceptance harness is exactly the case where a non-loopback bind is required, so this was worth fixing before running the real private-Cloud-Run proof.

### Exact changes made

#### 1. Optional inbound bearer authentication in the bridge

Updated `runtime/cloud_run_metrics_bridge.py`.

- Added `normalize_bridge_bearer_token()` with trimmed/non-empty validation and CR/LF rejection.
- Added optional `bearer_token` to `make_server()` and CLI/env support through `--bearer-token` / `STAGEGUARD_BRIDGE_BEARER_TOKEN`.
- `/readyz` and `/metrics` require the configured bearer credential before they can call `client.fetch()`.
- Bearer comparison uses `hmac.compare_digest`.
- Missing/wrong credentials return sanitized HTTP `401`, body `unauthorized\n`, and a Bearer challenge.
- Unauthorized requests terminate before Google ID-token acquisition/upstream Cloud Run access.
- `/healthz` remains unauthenticated process-only liveness and never reaches upstream.
- Existing loopback/default behavior remains backward-compatible when no inbound token is configured.
- The inbound scrape credential is explicitly independent from the Google Cloud Run ID token; caller authorization is never forwarded upstream.

Commit: `708e6c533a73e8814a6f432aa968bbd245ec67c5`.

#### 2. Ephemeral authentication in the disposable Cloud Run acceptance

Updated `runtime/cloud_run_metrics_acceptance.py`.

- Generates a fresh `secrets.token_urlsafe(32)` local bridge credential for each acceptance run.
- Starts the Docker-reachable `0.0.0.0` bridge with that credential.
- Uses the same credential for both readiness checks and the same-port bridge restart.
- Adds a Prometheus scrape `authorization` stanza containing only the ephemeral local credential.
- Keeps the Google Cloud Run ID token entirely inside `CloudRunMetricsClient`; Prometheus never receives it.
- The local credential exists only in memory plus the temporary read-only Prometheus config and is never printed.
- The temporary directory cleanup removes that config after the acceptance scope exits.
- Preserves the non-destructive proof sequence: anonymous Cloud Run rejection -> authenticated Cloud Run metrics validation -> Prometheus `up=1` -> local bridge stopped -> `up=0` -> authenticated upstream still valid -> same-port bridge restart -> `up=1`.

Commit: `fa2adbd1c26224ac9c3e217c4450fa88a86801c0`.

#### 3. Added focused inbound-auth regressions

Created `runtime/tests/test_cloud_run_metrics_bridge_inbound_auth.py`.

Coverage requires:
- malformed bridge bearer configuration to fail closed;
- `/healthz` to remain process-only while `/readyz` and `/metrics` require bearer auth when configured;
- missing/wrong bearer requests to cause zero upstream calls;
- the correct bearer to expose the validated metrics payload;
- generated Prometheus config to contain only the local scrape credential and not a Cloud Run token/upstream hostname;
- the disposable acceptance flow to reuse one generated local credential across initial bridge, readiness, temporary Prometheus config, and same-port restart while preserving exactly two explicit upstream acceptance fetches.

Commit: `3074427683eddcbc3d0d8e3c96dc429e7d06233d`.

#### 4. Updated bridge safety documentation

Updated `docs/cloud-run-metrics-bridge-safety.md` to document:
- the separate inbound scrape and upstream Cloud Run trust boundaries;
- recommended bearer protection for intentional non-loopback binds;
- 401/no-upstream-call behavior;
- Prometheus `authorization` configuration;
- the ephemeral acceptance credential lifecycle;
- the revised private Cloud Run acceptance proof and new regression module.

Commit: `fddf895b4fac4f97727bd5a2b94e0daabc546b5f`.

### Research / attribution

Checked current official Google Cloud Run authentication guidance and Prometheus configuration documentation before choosing the boundary:
- Cloud Run invocation uses Google-signed ID tokens whose audience identifies the receiving service or configured custom audience.
- Prometheus scrape configuration supports an `authorization` block with bearer credentials.

The repository documentation records the corresponding official references rather than introducing a custom token forwarding mechanism.

### Checks / results

- Re-read the production bridge commit diff and confirmed unauthorized bridge requests are rejected before `_upstream_ready()` / `client.fetch()` and therefore before Cloud Run credential use.
- Re-read the acceptance-harness diff and confirmed the generated bridge credential is passed to the initial bridge, readiness request, temporary Prometheus configuration, restart bridge, and recovery readiness request.
- Reviewed existing bridge and acceptance tests for API compatibility: new parameters are optional, so existing loopback/default test paths remain valid in source.
- The execution environment still cannot resolve `github.com` for a local checkout, so the new and existing Python test modules could not be executed here.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, remediation provider, incident, audit store, or other external runtime resource was changed.

No new green test-suite, Docker, or live Cloud Run acceptance claim is made.

### Decisions

1. Keep inbound bridge authentication optional for backward-compatible loopback/private deployments, but make the disposable acceptance harness always use it because that harness intentionally binds beyond loopback.
2. Do not forward caller credentials upstream. The local scrape token and Google ID token are separate trust domains.
3. Reject unauthorized requests before token minting/upstream access, reducing both credential use and attack surface.
4. Keep `/healthz` unauthenticated because it is process-only and does not inspect telemetry or mint an upstream token.
5. Use Prometheus's native `authorization` scrape configuration rather than placing the bearer in URL parameters or inventing a custom header convention.
6. Continue avoiding noisy CI solely to work around transient checkout/DNS failure.

### Blockers / unknowns

- `runtime/tests/test_cloud_run_metrics_bridge_inbound_auth.py` still needs an executable run.
- The existing bridge, acceptance, audience-boundary, redirect, and sentinel-family modules need a current combined run after this signature/config change.
- The execution-reconciliation/operator/Playwright safety set from the previous runs still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as checkout execution works, run `tests.test_cloud_run_metrics_bridge_inbound_auth`, `tests.test_cloud_run_metrics_bridge`, `tests.test_cloud_run_metrics_acceptance`, `tests.test_cloud_run_metrics_bridge_audience_boundary`, `tests.test_cloud_run_metrics_bridge_redirects`, and `tests.test_cloud_run_metrics_bridge_sentinel_family` together. If that boundary is green, run the pending execution-reconciliation/operator/Playwright safety set and then perform the real private Cloud Run `ADC -> /metrics -> authenticated bridge -> Prometheus up 1 -> 0 -> 1` acceptance without changing IAM or service lifecycle state.**
