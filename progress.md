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
- A metrics bridge bound beyond loopback requires explicit network-bind opt-in, inbound bearer authentication, strict bearer-token syntax, and a minimum 32-character credential.
- The reference Grafana MCP dependency is version-pinned and its server-side write/proxy restrictions are regression-locked alongside the pin.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; the newly pinned `1.4.1` still requires an executable smoke before a production-ready claim.
- Baseline incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

## Recent retained hardening

- Composite lifecycle safety states and bounded `sg-<40 lowercase hex>` reconciliation references.
- Operator `DO NOT REPLAY REMEDIATION` interlocks and browser acceptance coverage for post-provider persistence uncertainty.
- Base/anchored snapshot-authority regressions preventing failed persistence from publishing uncommitted investigation, approval, or outcome state.
- Evidence-unavailable lifecycle and authenticated bypass regressions.
- Cloud Run metrics audience, redirect, sentinel-family, authenticated bridge, and disposable `up: 1 -> 0 -> 1` acceptance scaffolding.
- Separate inbound scrape credentials from upstream Google ID tokens.
- Non-loopback bridge listeners fail closed without explicit network binding plus inbound authentication.
- Official Grafana MCP upgraded to reviewed `v1.4.1` with exact image pin and least-privilege command regression coverage.

## Run log — 2026-09-12 — official Grafana MCP 1.4.1 compatibility upgrade

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- repository tree and current head (`5a3507b9c8ad0652df0ba85fbac7284a9547c2a9` at run start);
- `runtime/cloud_run_metrics_bridge.py`;
- `runtime/cloud_run_metrics_acceptance.py`;
- `runtime/tests/test_cloud_run_metrics_bridge_inbound_auth.py`;
- `runtime/tests/test_cloud_run_metrics_bridge_audience_boundary.py`;
- `docker-compose.yml`;
- `runtime/tests/test_observability_image_pins.py`;
- `docs/grafana-mcp-evidence-safety.md`;
- `README.md`;
- official `grafana/mcp-grafana` GitHub release metadata for `v1.4.0` and `v1.4.1`.

Direct authenticated GitHub repository access was available and every write was limited to `UnknownGod2011/Grafana`. No unrelated repository or external infrastructure was touched.

### Finding

The StageGuard reference stack still pinned the official Grafana MCP server at `1.3.0`, while the official upstream published `v1.4.1` on 2026-09-11.

Upstream compatibility review found:
- `v1.4.1` has a breaking input change for Sift tools (`find_error_pattern_logs` and `find_slow_requests` now use `labelSelector` instead of the previous `labels` map);
- StageGuard does not enable Sift; its MCP service exposes only `datasource,prometheus,loki`;
- the preceding `v1.4.0` added selective `--enable-write-tools` behavior under `--disable-write`, but StageGuard does not pass `--enable-write-tools`;
- StageGuard already retains `--disable-write`, `--disable-proxied`, and bounded Loki result configuration.

Therefore the upstream breaking change is outside StageGuard's configured evidence contract, but the existing tests did not lock the exact MCP version or the least-privilege command flags. A future image bump could therefore silently widen the server-side evidence plane without a focused regression failure.

Official release attribution:
- https://github.com/grafana/mcp-grafana/releases/tag/v1.4.1
- https://github.com/grafana/mcp-grafana/releases/tag/v1.4.0

### Exact changes made

#### 1. Upgraded the official Grafana MCP image pin

Updated `docker-compose.yml` from `grafana/mcp-grafana:1.3.0` to `grafana/mcp-grafana:1.4.1`.

- Preserved opt-in `mcp` profile behavior.
- Preserved `--disable-write`.
- Preserved `--enabled-tools datasource,prometheus,loki`.
- Preserved `--disable-proxied`.
- Preserved `--max-loki-log-limit 8`.
- Added an adjacent compatibility rationale documenting the 2026-09-11 release and why the Sift breaking change is outside StageGuard's enabled tool set.

Commit: `f8731116a57363ab302c529cb5f8504e63d537e3`.

#### 2. Regression-locked the MCP version and least-privilege surface

Updated `runtime/tests/test_observability_image_pins.py`.

New coverage requires:
- exact `grafana/mcp-grafana:1.4.1` pin;
- `--disable-write` to remain present;
- `--disable-proxied` to remain present;
- enabled tool categories to remain `datasource,prometheus,loki`;
- bounded Loki limit configuration to remain present;
- `--enable-write-tools` to remain absent;
- the compatibility rationale to stay next to the image pin.

This converts the read-only MCP server configuration from documentation-only intent into a focused regression contract.

Commit: `0293e834e332fd65237997db3db06c553c7f5885`.

#### 3. Updated MCP safety documentation and upstream attribution

Updated `docs/grafana-mcp-evidence-safety.md`.

- Changed the documented reference image to `1.4.1`.
- Added a reviewed dependency baseline with official upstream release/repository links.
- Recorded the `v1.4.1` Sift breaking change and why it does not affect StageGuard.
- Recorded the `v1.4.0` selective-write-tool addition and explicitly documented that StageGuard does not enable it.
- Added exact MCP pin + read-only/proxy/tool-surface preservation to regression expectations.
- Retained the existing strict metric/log parsing and evidence-unavailable fail-closed contracts.

Commit: `5dbaa671f2c17bccdf6e9931fbcac53c3c45df21`.

### Checks / results

- Queried the official `grafana/mcp-grafana` release API and confirmed `v1.4.1` was published 2026-09-11 and is the newest release found in the current release list.
- Reviewed official `v1.4.1` and `v1.4.0` release notes before changing the pin.
- Confirmed the documented `v1.4.1` breaking change is limited to Sift inputs, which are outside StageGuard's enabled `datasource,prometheus,loki` categories.
- Compared repository head against the run-start commit after implementation. The implementation diff is intentionally limited to three files: `docker-compose.yml` (+4/-2), `docs/grafana-mcp-evidence-safety.md` (+14/-2), and `runtime/tests/test_observability_image_pins.py` (+27/-0).
- Attempted local checkout/test execution again, but the execution environment still failed before checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No Docker image was pulled and no live MCP smoke was claimed because executable checkout/network access remains blocked in the local runner.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, remediation provider, incident, audit store, or other external runtime resource was changed.

No new green test-suite, Docker, live MCP, or live Cloud Run acceptance claim is made.

### Decisions

1. Upgrade to the current official Grafana MCP patch only after reviewing release compatibility against StageGuard's enabled tool categories.
2. Treat MCP command-line least privilege as an executable regression contract, not only documentation.
3. Keep all write tools disabled even though newer MCP versions support selective write re-enablement.
4. Keep proxied tools disabled and preserve the narrow `datasource,prometheus,loki` evidence surface.
5. Do not infer compatibility from version numbers alone; explicitly record upstream breaking changes and whether they intersect StageGuard's enabled surface.
6. Avoid noisy CI solely to work around the transient checkout/DNS failure.

### Blockers / unknowns

- `runtime.tests.test_observability_image_pins` still needs an executable run after the MCP pin change.
- A live read-only smoke against `grafana/mcp-grafana:1.4.1` is still required before calling the new dependency baseline production-ready.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set from previous runs still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout/Docker access works, run `runtime.tests.test_observability_image_pins` and the official read-only MCP smoke against `grafana/mcp-grafana:1.4.1` first. If both pass, run the six focused Cloud Run bridge modules, then the pending operator/Playwright safety set, and finally the private Cloud Run `ADC -> /metrics -> authenticated bridge -> Prometheus up 1 -> 0 -> 1` acceptance without changing IAM or service lifecycle state.**
