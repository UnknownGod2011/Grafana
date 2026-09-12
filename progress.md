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
- Browser/API surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- Runtime metric readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.
- A metrics bridge bound beyond loopback requires explicit network-bind opt-in, inbound bearer authentication, strict bearer-token syntax, and a minimum 32-character credential.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; server-side write/proxy restrictions are regression-locked; the live smoke rejects any advertised MCP tool that is not explicitly annotated `readOnlyHint=true`.
- Grafana MCP smoke requests are time-bounded, stdout JSON-RPC frames are individually bounded, strict framing/response integrity fails closed, and pending stdout frames are held in a fixed-capacity queue.
- Cloud Run remediation/recovery execution watchdog configuration is bounded to 1-600 seconds so operator configuration cannot effectively disable the watchdog with an arbitrarily large value.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject leading/trailing whitespace or control characters before runtime composition.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires an executable live smoke before a production-ready claim.
- Recent MCP hardening added request deadlines, strict JSON-RPC framing/response-ID validation, a 1,048,576-character frame cap, and a 16-frame pending stdout queue; the actual repository regression modules still need a runnable checkout.

## Run log — 2026-09-12 — Cloud Run production safety bounds

### Inspected at start

Read this `progress.md` completely before choosing work. Inspected the current default branch and reviewed:
- `README.md`
- `runtime/api.py`
- `runtime/tests/test_api.py`
- `runtime/cloudrun_entrypoint.py`
- `runtime/tests/test_cloudrun_entrypoint.py`
- `runtime/bootstrap.py`
- `GOOGLE_CLOUD_DEPLOYMENT.md`
- `scripts/deploy_cloud_run.sh`
- current recent commits; run-start head was `b93a9d6abc52b3e2c528218316c2e777d8e1c4f8`.

All repository writes were limited to `UnknownGod2011/Grafana`. No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, or remediation provider was modified.

### Findings

1. `runtime/cloudrun_entrypoint.py` accepted any finite positive `STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS`. A very large value could make the remediation watchdog operationally meaningless even though the code still considered it enabled.
2. The checkpoint HMAC guard enforced only a minimum 32-byte length. It did not cap pathological secret size or reject accidental boundary whitespace/control characters. Because this secret authenticates persisted lifecycle authority, production composition should reject obviously malformed values early.
3. `scripts/deploy_cloud_run.sh` independently validated the watchdog as merely positive, so deployment-time validation could accept a value that the hardened runtime would later reject.
4. `GOOGLE_CLOUD_DEPLOYMENT.md` still named the older `grafana/mcp-grafana:1.3.0` image even though the repository is now pinned to 1.4.1.

### Exact changes made

#### 1. Bounded Cloud Run watchdog and checkpoint HMAC configuration

Commits:
- `4380b8a5803e2a51d86bba8f233946abd4e6f8ac`
- `c1f34ad9b72d46a5868fe69e28f7c14072922147`

`runtime/cloudrun_entrypoint.py` now:
- accepts remediation/recovery execution watchdog values only from 1 through 600 seconds, inclusive;
- rejects blank, malformed, non-finite, sub-second, and above-10-minute values with one bounded startup error;
- requires checkpoint HMAC keys to be 32-512 UTF-8 bytes;
- rejects leading/trailing whitespace and ASCII control characters in the checkpoint HMAC key before constructing production bootstrap arguments;
- reads the raw checkpoint secret for validation rather than passing through `_required()`, which strips whitespace and would have hidden malformed boundary whitespace.

The raw-secret correction was made immediately after inspection caught that `_required()` normalization would otherwise make the new whitespace regression ineffective.

#### 2. Added focused Cloud Run regressions

Commit: `adf8b2ad8c934a8fa3257d40afa9afef6efa014b`

`runtime/tests/test_cloudrun_entrypoint.py` now covers:
- accepted watchdog boundaries and representative in-range values (`1`, `17.5`, `600`);
- rejected values including zero, sub-second, above-600, negatives, NaN/infinities, blanks, and malformed strings;
- HMAC keys below 32 bytes and above 512 bytes;
- leading/trailing whitespace and embedded control-character rejection;
- continued acceptance of a bounded 32-byte key and GCS checkpoint composition.

#### 3. Aligned deployment-time validation with runtime validation

Commit: `d9a21fed9f578b36a75ddbf30c60c945d2f49781`

`scripts/deploy_cloud_run.sh` now enforces the same inclusive 1-600 second watchdog range before invoking `gcloud`, rather than accepting any positive finite number. This prevents a deployment command from succeeding only for the container to refuse startup with stricter runtime validation.

#### 4. Updated production deployment documentation

Commit: `dfe3805196f2e961e00292607dc607b9cf96255c`

`GOOGLE_CLOUD_DEPLOYMENT.md` now:
- names the current official Grafana MCP baseline `grafana/mcp-grafana:1.4.1`;
- documents the 1-600 second watchdog safety range and fail-closed behavior;
- documents the 32-512 byte checkpoint HMAC bounds plus whitespace/control-character rejection;
- includes the watchdog environment variable in optional deployment configuration;
- updates failure behavior to match the executable production guardrails.

### Checks / results

- Direct authenticated GitHub repository inspection and all repository writes succeeded.
- A fresh executable checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`; the execution environment still failed with `Could not resolve host: github.com` before tests could run.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- An isolated Python proof of the exact new watchdog/HMAC predicates passed: accepted `1`, `17.5`, `600`, and a 32-byte key; rejected all configured out-of-range/non-finite watchdog cases and short/oversized/whitespace/control-character HMAC cases.
- Because the actual repository checkout remains unavailable, `runtime.tests.test_cloudrun_entrypoint` and shell-level deployment tests were not executed from the repository. There is no new repository-suite green claim.

### Decisions

1. Treat an excessively large watchdog as a production safety misconfiguration rather than a valid customization; 10 minutes is the hard ceiling for this live remediation/recovery guardrail.
2. Keep runtime and deployment-helper validation identical so bad configuration fails before cloud mutation whenever possible.
3. Validate the raw checkpoint HMAC environment value before normalization because normalization can hide malformed secret boundaries.
4. Bound checkpoint secret size as well as minimum length; this is a persisted-authority credential and production configuration should have a finite input envelope.
5. Continue avoiding noisy GitHub Actions merely to work around the transient local DNS/checkout issue.

### Blockers / unknowns

- `runtime.tests.test_cloudrun_entrypoint` must be run from an actual checkout to verify the committed regression module and imports end-to-end.
- Any existing shell/deployment-helper tests should be run against the updated 1-600 second validation.
- `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins` still need an actual repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set from previous runs still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout is available, run `runtime.tests.test_cloudrun_entrypoint` plus any deploy-script regression suite first to verify the new runtime/deployment safety bounds. Then run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke. If those are clean, proceed to the six Cloud Run bridge modules and the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
