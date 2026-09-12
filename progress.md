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
- The reference Grafana MCP dependency is version-pinned; server-side write/proxy restrictions are regression-locked; the live smoke rejects any advertised MCP tool that is not explicitly annotated `readOnlyHint=true`.
- Grafana MCP smoke requests are bounded so a started-but-silent subprocess cannot hang release/operator acceptance indefinitely.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires an executable live smoke before a production-ready claim.
- Baseline incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

## Recent retained hardening

- Composite lifecycle safety states and bounded `sg-<40 lowercase hex>` reconciliation references.
- Operator `DO NOT REPLAY REMEDIATION` interlocks and browser acceptance coverage for post-provider persistence uncertainty.
- Base/anchored snapshot-authority regressions preventing failed persistence from publishing uncommitted investigation, approval, or outcome state.
- Evidence-unavailable lifecycle and authenticated bypass regressions.
- Cloud Run metrics audience, redirect, sentinel-family, authenticated bridge, and disposable `up: 1 -> 0 -> 1` acceptance scaffolding.
- Separate inbound scrape credentials from upstream Google ID tokens.
- Non-loopback bridge listeners fail closed without explicit network binding plus strong inbound authentication.
- Official Grafana MCP upgraded to reviewed `v1.4.1` with exact image pin and least-privilege command regression coverage.
- Live MCP registry validation requires all advertised tools to be explicitly read-only.

## Run log — 2026-09-12 — bounded Grafana MCP smoke execution

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected the repository root/runtime tree, `runtime/mcp_smoke.py`, `runtime/tests/test_mcp_smoke_surface.py`, and `docs/grafana-mcp-evidence-safety.md`. Also reviewed current upstream Grafana MCP annotation work and official repository guidance relevant to the evidence-only tool boundary.

All repository writes in this run were limited to `UnknownGod2011/Grafana`. No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, or remediation provider was modified.

### Finding

The newly strengthened live MCP smoke failed closed on unsafe/malformed tool registration, but its stdio request path still used blocking `readline()` with no protocol deadline. If the MCP subprocess started successfully and then stopped replying to `initialize`, `tools/list`, or `tools/call`, the acceptance command could hang indefinitely instead of producing a bounded failure.

For a production release check this is a reliability and operational-safety gap: dependency health must include bounded response behavior, not only tool semantics after a response eventually arrives.

Relevant upstream references reviewed:
- https://github.com/grafana/mcp-grafana
- https://github.com/grafana/mcp-grafana/issues/1009 (upstream work requiring explicit MCP tool annotations; reinforces why StageGuard validates the effective advertised registry rather than assuming annotations/configuration intent)

### Exact changes made

#### 1. Bounded every stdio JSON-RPC request

Commits:
- `20c6048dc9a7fd43510b77ad9b3e557660a0a9a1`
- `62af4832ead5a032ac3890d9ca6c23772ed4b939`

`runtime/mcp_smoke.py` now:
- uses a dedicated daemon stdout-reader thread and queue rather than blocking the request path directly on `readline()`;
- applies a monotonic deadline to each JSON-RPC request;
- defaults to a 15-second per-request timeout;
- supports `STAGEGUARD_MCP_REQUEST_TIMEOUT_SECONDS` for explicit tuning;
- rejects nonnumeric, non-finite, non-positive, or >120-second timeout configuration;
- reports which MCP method timed out without dumping credentials/provider data;
- turns broken stdin writes into bounded `McpError` failures;
- terminates and, if necessary, kills an unresponsive subprocess during cleanup;
- joins/closes the stdout reader cleanly to avoid leaked pipe handles.

The existing all-tools `readOnlyHint=true` registry gate and real datasource/Prometheus query remain unchanged.

#### 2. Added dependency-free timeout regressions

Created `runtime/tests/test_mcp_smoke_timeout.py`.

Commit: `f71c389bc607b9e60f0efd1828e4954645f60788`.

Coverage includes:
- default and explicit timeout parsing;
- invalid/unsafe timeout configuration;
- a real local Python subprocess returning a matching JSON-RPC response;
- a real local Python subprocess that deliberately remains silent, proving request timeout rather than indefinite blocking;
- constructor rejection of non-positive/non-finite timeout values.

The test requires no Docker, Grafana, token, or external service.

#### 3. Documented bounded smoke behavior

Updated `docs/grafana-mcp-evidence-safety.md`.

Commit: `7b12a33e0271e5cc7d0852a266517b044335a603`.

The document now records the 15-second default/120-second maximum, the environment override, fail-closed invalid configuration, subprocess cleanup behavior, and the expectation that timeout/cleanup behavior remains regression-covered.

### Checks / results

- Direct authenticated GitHub repository inspection and writes succeeded.
- A fresh local repository checkout was attempted for `runtime.tests.test_mcp_smoke_surface` + `runtime.tests.test_mcp_smoke_timeout`, but the execution environment still failed at clone time with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- Because checkout remained unavailable, I built a dependency-free local mirror of the new `StdioClient` timeout path and exercised the responsive/silent subprocess behavior directly. Result: **3/3 passed**.
- The first mirror run exposed a `ResourceWarning` for an unclosed stdout pipe; the production implementation was then hardened to join the reader and close stdout. Re-running the mirror with `ResourceWarning` promoted to an error passed **3/3** without warnings.
- No Docker image was pulled and no live MCP 1.4.1 smoke was claimed.

Therefore there is still **no new green repository-suite claim**. The protocol mechanics were executable-tested in isolation, while the committed unit modules and real MCP stack still need execution from a functioning checkout.

### Decisions

1. MCP acceptance must be bounded in time as well as bounded in capability.
2. Use a platform-neutral reader thread/queue instead of `select()` on subprocess pipes so the smoke remains usable on Windows and Unix-like development hosts.
3. Put a hard maximum on operator-configurable request deadlines so a typo cannot silently restore effectively unbounded waiting.
4. Keep timeouts per request, not one global smoke deadline, so slow startup/query phases are diagnosable by method while still bounded.
5. Preserve the all-tools explicit-read-only gate; timeout hardening does not relax dependency security.
6. Avoid noisy CI solely to work around the transient checkout/DNS failure.

### Blockers / unknowns

- `runtime.tests.test_mcp_smoke_surface`, `runtime.tests.test_mcp_smoke_timeout`, and `runtime.tests.test_observability_image_pins` still need execution from the actual repository checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- It remains to confirm that every tool actually exposed by 1.4.1 under StageGuard's exact `datasource,prometheus,loki --disable-write --disable-proxied` configuration carries `readOnlyHint=true`.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set from previous runs still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable repository checkout/Docker access works, run `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins`, then execute `python runtime/mcp_smoke.py` against the pinned Grafana MCP 1.4.1 stack. This must prove both bounded request behavior and an all-explicit-read-only live registry while successfully querying StageGuard Prometheus evidence. If clean, continue with the six focused Cloud Run bridge modules and the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up 1 -> 0 -> 1` acceptance.**
