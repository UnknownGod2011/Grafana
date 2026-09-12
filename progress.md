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

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Baseline incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

## Recent retained hardening

- Composite lifecycle safety states and bounded `sg-<40 lowercase hex>` reconciliation references.
- Operator `DO NOT REPLAY REMEDIATION` interlocks and browser acceptance coverage for post-provider persistence uncertainty.
- Base/anchored snapshot-authority regressions preventing failed persistence from publishing uncommitted investigation, approval, or outcome state.
- Evidence-unavailable lifecycle and authenticated bypass regressions.
- Cloud Run metrics audience, redirect, sentinel-family, authenticated bridge, and disposable `up: 1 -> 0 -> 1` acceptance scaffolding.
- Separate inbound scrape credentials from upstream Google ID tokens.
- Non-loopback bridge listeners fail closed without explicit network binding plus inbound authentication.

## Run log — 2026-09-12 — strong non-loopback bridge bearer credentials

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/cloud_run_metrics_bridge.py`;
- `runtime/cloud_run_metrics_acceptance.py`;
- `runtime/tests/test_cloud_run_metrics_bridge_inbound_auth.py`;
- `docs/cloud-run-metrics-bridge-safety.md`;
- recent repository commit diffs after each write.

Direct authenticated GitHub repository access was available and every write was limited to `UnknownGod2011/Grafana`. No unrelated repository or external infrastructure was touched.

### Finding

The previous run correctly made authentication mandatory for non-loopback bridge listeners, but the credential boundary still accepted values such as a one-character token or header-ambiguous strings. That left two avoidable production risks:

1. an operator could expose a network-reachable bridge with an obviously weak shared secret while satisfying the nominal authentication requirement;
2. internal whitespace, Unicode, separators, or other malformed values could survive configuration and fail later at HTTP-header handling rather than being rejected before listener construction.

The disposable acceptance harness already generates a strong `secrets.token_urlsafe(32)` credential, so tightening the production boundary is compatible with the intended private Cloud Run acceptance path.

### Exact changes made

#### 1. Hardened bridge bearer-token normalization

Updated `runtime/cloud_run_metrics_bridge.py`.

- Added an explicit ASCII bearer/token68-style character-set validator.
- Allowed characters are letters, digits, `.`, `_`, `~`, `+`, `/`, `-`, with optional trailing `=` padding.
- Whitespace, CR/LF, commas, Unicode, and other header-ambiguous values now fail configuration before listener creation.
- Added `MIN_NETWORK_BEARER_TOKEN_LENGTH = 32`.
- Non-loopback listeners now require a normalized inbound bearer of at least 32 characters in addition to the existing `--allow-network-bind` opt-in and authentication requirement.
- Loopback-only development retains optional authentication and may still use shorter valid local credentials.
- CLI help/module documentation now states the non-loopback minimum explicitly.

Commit: `3e9b119f6e2db5278e68650507df49be19f9f61b`.

#### 2. Strengthened inbound-auth regression coverage

Updated `runtime/tests/test_cloud_run_metrics_bridge_inbound_auth.py`.

Coverage now requires:
- malformed/ambiguous bearer values to fail normalization;
- a 31-character credential to fail on `0.0.0.0` even with network-bind opt-in;
- a strong credential to reach server construction;
- loopback to retain backward-compatible short local credentials;
- authenticated `/metrics` behavior, zero upstream calls for unauthorized requests, Prometheus credential separation, and same-token acceptance restart behavior to remain covered.

Commit: `a8b3b42bc9f579021f2462c6dcb5669d3f745248`.

#### 3. Updated bridge safety documentation

Updated `docs/cloud-run-metrics-bridge-safety.md`.

- Documented the enforced three-part non-loopback boundary: explicit bind opt-in, inbound authentication, and a minimum 32-character credential.
- Documented accepted token syntax and rejection of ambiguous values.
- Clarified that minimum length is only a guardrail and production secrets should still be randomly generated.
- Documented `secrets.token_urlsafe(32)` as the acceptance harness pattern.
- Retained the separate inbound-scrape vs upstream Google-ID-token trust model, redirect rejection, audience matching, sentinel validation, and least-privilege guidance.

Commit: `1d7eb1094a875526676e39f4efc05f07c52b82ee`.

### Checks / results

- Re-read the committed production diff and confirmed token normalization and minimum-length enforcement occur before `ThreadingHTTPServer(...)` construction.
- Re-read the committed regression diff and confirmed it covers malformed token syntax, the 31-character network failure boundary, strong-token construction, and loopback compatibility.
- Confirmed the disposable acceptance harness still generates `secrets.token_urlsafe(32)`, which comfortably satisfies the new minimum and accepted character set.
- Attempted a fresh local checkout and the focused six-module bridge suite:
  - `tests.test_cloud_run_metrics_bridge_inbound_auth`
  - `tests.test_cloud_run_metrics_bridge`
  - `tests.test_cloud_run_metrics_acceptance`
  - `tests.test_cloud_run_metrics_bridge_audience_boundary`
  - `tests.test_cloud_run_metrics_bridge_redirects`
  - `tests.test_cloud_run_metrics_bridge_sentinel_family`
- The execution environment still failed before checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, remediation provider, incident, audit store, or other external runtime resource was changed.

No new green test-suite, Docker, or live Cloud Run acceptance claim is made.

### Decisions

1. Treat network-reachable scrape authentication as a credential-quality boundary, not merely a non-empty-string check.
2. Reject malformed bearer/header values at configuration time rather than allowing them to fail later in request handling.
3. Use 32 characters as a minimum guardrail while explicitly avoiding claims that length alone proves entropy.
4. Preserve lightweight loopback development behavior because it does not widen network exposure.
5. Keep inbound scrape credentials and upstream Google ID tokens in separate trust domains.
6. Avoid noisy CI solely to work around the transient checkout/DNS failure.

### Blockers / unknowns

- The strengthened inbound-auth regression and focused six-module Cloud Run bridge suite still need an executable run.
- The execution-reconciliation/operator/Playwright safety set from previous runs still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as checkout execution works, run the six focused Cloud Run bridge/auth/audience/redirect/sentinel/acceptance modules together. If green, run the pending execution-reconciliation/operator/Playwright safety set and then perform the real private Cloud Run `ADC -> /metrics -> authenticated bridge -> Prometheus up 1 -> 0 -> 1` acceptance without changing IAM or service lifecycle state.**
