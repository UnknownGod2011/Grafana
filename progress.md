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
- The reference Grafana MCP dependency is version-pinned; server-side write/proxy restrictions are regression-locked; the live smoke now also rejects any advertised MCP tool that is not explicitly annotated `readOnlyHint=true`.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
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

## Run log — 2026-09-12 — live Grafana MCP tool-surface hardening

### Inspected at start

Read the previous `progress.md` completely before deciding what to change. Inspected the current repository/default branch, `runtime/mcp_smoke.py`, `runtime/tests/test_observability_image_pins.py`, `docs/grafana-mcp-evidence-safety.md`, `README.md`, the runtime tree, and the official Grafana MCP documentation/upstream guidance relevant to `--disable-write` and `--enable-write-tools`.

All repository writes were limited to `UnknownGod2011/Grafana`. No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, or remediation provider was modified.

### Finding

The reference stack statically pins `grafana/mcp-grafana:1.4.1` and regression-locks `--disable-write`, `--disable-proxied`, `datasource,prometheus,loki`, and the absence of `--enable-write-tools`. However, the live MCP smoke only required `list_datasources` and `query_prometheus` to advertise `readOnlyHint=true`.

That left an upgrade/runtime drift gap: the server could theoretically register an additional write-capable or ambiguously annotated tool while the two required reads still passed the smoke. Static Compose assertions would not prove the effective runtime tool registry remained evidence-only.

Current upstream guidance confirms that write tools are expected to respect `--disable-write` and that `--enable-write-tools` selectively re-enables individual tools. StageGuard intentionally does not use that escape hatch.

Relevant upstream references reviewed:
- https://github.com/grafana/mcp-grafana
- https://github.com/grafana/mcp-grafana/blob/main/CONTRIBUTING.md

### Exact changes made

#### 1. Hardened `runtime/mcp_smoke.py`

Commit: `2e4c361f1fffd736a74313309b776d065439834d`.

The smoke now:
- validates that `tools/list` contains a list rather than accepting malformed shapes;
- requires every tool entry to be an object with a non-empty string name;
- rejects duplicate tool names;
- still requires `list_datasources` and `query_prometheus`;
- rejects **any advertised tool** whose `annotations.readOnlyHint` is absent or not exactly `true`;
- performs the real datasource and Prometheus query only after the complete advertised surface passes that read-only gate;
- reports the bounded sorted advertised read-only tool names on success for operator/release evidence.

This makes the smoke fail closed on effective runtime tool-registration drift instead of trusting configuration intent alone.

#### 2. Added dependency-free smoke-surface regressions

Created `runtime/tests/test_mcp_smoke_surface.py`.

Commit: `e05bcbc55e48b0cb3e46e10ae6a6a7ac3cd54f8c`.

Coverage includes:
- valid required + optional explicit read-only tools;
- missing required read tools;
- `readOnlyHint=false`;
- missing/invalid annotations;
- malformed `tools` field;
- malformed tool entries;
- missing, blank, or non-string names;
- duplicate advertised names.

The tests exercise pure validation functions and require no Grafana, Docker, token, or MCP process.

#### 3. Updated MCP evidence-safety documentation

Commit: `69d6685dafda5a88b65f1e8457482af4643736e7`.

`docs/grafana-mcp-evidence-safety.md` now documents the live server surface contract and explicitly states that missing `readOnlyHint` is treated the same as `false`. It also clarifies that annotation validation is defense in depth and does not replace server-side `--disable-write`, `--disable-proxied`, narrow categories, or least-privilege Grafana credentials.

### Checks / results

- Direct authenticated GitHub repository inspection and writes succeeded.
- Reviewed current official/upstream Grafana MCP read-only/write-tool behavior before implementing the guard.
- Attempted a fresh local checkout followed by:
  - `python -m unittest runtime.tests.test_observability_image_pins runtime.tests.test_mcp_smoke_surface`
- The local execution environment again failed before checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- No Docker image was pulled and no live MCP 1.4.1 smoke was claimed.

Therefore there is **no new green executable-test claim** for this run. The implementation is committed, but focused unit execution and the real MCP 1.4.1 smoke remain required.

### Decisions

1. Validate the effective live MCP tool registry, not only Compose flags.
2. Treat missing read-only annotations as unsafe/ambiguous for StageGuard's evidence-only boundary.
3. Apply the invariant to every advertised tool, including future optional datasource/Prometheus/Loki tools, so upstream registration drift cannot hide behind the two required tools.
4. Keep the live query in the same smoke so release acceptance proves both capability and least privilege.
5. Preserve server-side controls and credential least privilege; MCP annotations are an additional guard, not an authorization mechanism.
6. Avoid noisy CI solely to work around the transient checkout/DNS failure.

### Blockers / unknowns

- `runtime.tests.test_mcp_smoke_surface` and `runtime.tests.test_observability_image_pins` still need executable local runs.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- It remains to confirm that every tool actually exposed by 1.4.1 under StageGuard's exact `datasource,prometheus,loki --disable-write --disable-proxied` configuration carries `readOnlyHint=true`; if upstream omits an annotation on a genuinely read-only tool, the smoke will intentionally fail and the compatibility decision must be explicit rather than silently relaxed.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set from previous runs still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout/Docker access works, run `runtime.tests.test_observability_image_pins` and `runtime.tests.test_mcp_smoke_surface`, then execute `python runtime/mcp_smoke.py` against the repository-pinned Grafana MCP 1.4.1 stack. If the live tool registry passes the all-tools `readOnlyHint=true` gate and the Prometheus query succeeds, continue with the six focused Cloud Run bridge modules and private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up 1 -> 0 -> 1` acceptance.**
