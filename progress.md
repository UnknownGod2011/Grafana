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
- A metrics bridge bound beyond loopback requires explicit network-bind opt-in and inbound bearer authentication; loopback-only binds may remain unauthenticated for local development.

## Recent hardening retained

- `ExecutionSafeIncidentService` prioritizes execution uncertainty once provider dispatch may have occurred.
- Authenticated lifecycle responses expose bounded composite safety state and, only when appropriate, strict `sg-<40 lowercase hex>` reconciliation references.
- `/readyz`, Prometheus, and the operator console consistently expose no-replay state without exporting high-cardinality reconciliation identifiers through metrics.
- `execution_uncertain_audit_failed` renders `DO NOT REPLAY REMEDIATION` and disables lifecycle mutation controls.
- Base and anchored checkpoint-backed transition failures restore the last committed snapshot and keep append-before-persistence residue out of committed operator history.
- Authenticated evidence-unavailable briefing/approval/execution bypass attempts fail closed with no Gemini or remediation side effects.
- The Cloud Run metrics bridge rejects ID-token-bearing redirects, validates target/audience boundaries, validates an unambiguous StageGuard sentinel, and separates inbound scrape authentication from the upstream Cloud Run ID token.
- Non-loopback metrics bridge listeners now fail closed unless both `--allow-network-bind` and a valid inbound bearer credential are present.
- The disposable private-Cloud-Run acceptance harness generates one fresh local scrape credential per run so its required `0.0.0.0` Docker-reachable bridge is never anonymously readable.

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
- Added separate inbound bearer authentication for the local/private metrics bridge and ephemeral Prometheus scrape credentials in the disposable acceptance harness.

## Run log — 2026-09-12 — mandatory authentication for non-loopback metrics bridge binds

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/cloud_run_metrics_bridge.py`;
- `runtime/cloud_run_metrics_acceptance.py` including `_start_bridge()` and the disposable restart flow;
- `runtime/tests/test_cloud_run_metrics_bridge.py`;
- `runtime/tests/test_cloud_run_metrics_bridge_inbound_auth.py`;
- `docs/cloud-run-metrics-bridge-safety.md`.

Direct authenticated GitHub repository access was available and all writes were limited to `UnknownGod2011/grafana`. No unrelated repository or external infrastructure was touched.

### Finding

The previous run added optional inbound bearer authentication and made the disposable acceptance harness use it. However, the production `make_server()` contract still allowed this configuration:

`host=0.0.0.0`, `allow_network_bind=True`, `bearer_token=None`.

That meant an operator could explicitly enable a non-loopback listener yet accidentally expose `/readyz` and `/metrics` anonymously. The documentation recommended bearer protection, but the production boundary did not enforce it. Since the bridge exists specifically to protect a private authenticated StageGuard metrics path, relying on operator memory at the network exposure boundary was unnecessarily weak.

### Exact changes made

#### 1. Fail closed on unauthenticated non-loopback bridge listeners

Updated `runtime/cloud_run_metrics_bridge.py`.

- `make_server()` now determines whether the requested host is loopback before constructing the server.
- Non-loopback binds require the existing explicit `allow_network_bind=True` opt-in.
- After bearer normalization, non-loopback binds additionally require a non-`None` inbound bearer credential.
- Missing authentication raises `BridgeConfigurationError` before `ThreadingHTTPServer` is created, so an anonymous listener is never opened.
- Loopback-only binds retain backward-compatible optional bearer authentication for local development.
- Updated module and CLI help text to make the mandatory non-loopback requirement explicit.

Commit: `44e1663149dfa0843a4d13d5cdbd1bba428e61f2`.

#### 2. Added explicit non-loopback auth regression

Updated `runtime/tests/test_cloud_run_metrics_bridge_inbound_auth.py`.

The new regression requires:
- non-loopback bind without network opt-in to fail;
- non-loopback bind with opt-in but no bearer credential to fail;
- non-loopback bind with both opt-in and a valid bearer credential to reach server construction;
- the configured handler to receive exactly that inbound credential.

The successful construction branch mocks `ThreadingHTTPServer`, avoiding a real wildcard listener in the regression itself.

Commit: `d8f3799a4f5f8cfdcb04d6fdd866fe93a6b36efd`.

#### 3. Updated bridge safety documentation

Updated `docs/cloud-run-metrics-bridge-safety.md`.

- Changed non-loopback authentication from a recommendation to an enforced invariant.
- Documented that `make_server()` rejects an unauthenticated network bind before listener creation.
- Clarified that loopback remains the only mode where inbound auth is optional.
- Updated fail-closed behavior and regression-coverage sections accordingly.

Commit: `80bd44dc024e26fc4d71c4253ac3450d458b522f`.

### Checks / results

- Re-read the production construction path and confirmed bearer normalization occurs before server creation and the new non-loopback/no-token rejection precedes `ThreadingHTTPServer(...)`.
- Confirmed the disposable Cloud Run acceptance already supplies the same generated bearer credential to both initial and restarted `0.0.0.0` bridge instances, so the stronger invariant is compatible with that path in source.
- Confirmed loopback `make_server()` calls in existing bridge tests remain valid because authentication is still optional there.
- Attempted a fresh local checkout and the focused six-module bridge suite:
  - `tests.test_cloud_run_metrics_bridge_inbound_auth`
  - `tests.test_cloud_run_metrics_bridge`
  - `tests.test_cloud_run_metrics_acceptance`
  - `tests.test_cloud_run_metrics_bridge_audience_boundary`
  - `tests.test_cloud_run_metrics_bridge_redirects`
  - `tests.test_cloud_run_metrics_bridge_sentinel_family`
- The execution environment again failed before checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, remediation provider, incident, audit store, or other external runtime resource was changed.

No new green test-suite, Docker, or live Cloud Run acceptance claim is made.

### Decisions

1. Treat non-loopback binding as a security boundary, not merely an operator convenience: explicit bind opt-in is necessary but no longer sufficient without inbound authentication.
2. Preserve simple unauthenticated loopback development because it does not widen network exposure and existing local workflows depend on it.
3. Keep `/healthz` process-only and unauthenticated; it does not access telemetry, mint a Cloud Run token, or disclose upstream state.
4. Keep inbound scrape credentials and upstream Google ID tokens in separate trust domains.
5. Avoid noisy CI solely to work around the transient checkout/DNS failure.

### Blockers / unknowns

- The strengthened inbound-auth regression and the focused six-module Cloud Run bridge suite still need an executable run.
- The execution-reconciliation/operator/Playwright safety set from previous runs still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as checkout execution works, run the six focused Cloud Run bridge/auth/audience/redirect/sentinel/acceptance modules together. If green, run the pending execution-reconciliation/operator/Playwright safety set and then perform the real private Cloud Run `ADC -> /metrics -> authenticated bridge -> Prometheus up 1 -> 0 -> 1` acceptance without changing IAM or service lifecycle state.**
