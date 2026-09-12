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
- Cloud Run remediation/recovery execution watchdog configuration is bounded to 1-600 seconds.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject leading/trailing whitespace or control characters before runtime composition.
- The Cloud Run deployment helper has a hermetic shell regression boundary that rejects unsafe watchdog values before any `gcloud` invocation.
- Telemetry profiles now require genuinely independent healthy comparators: `healthy_uplink` cannot equal `affected_uplink`, `healthy_peer_feeds` cannot include the affected feed, and healthy peer feeds cannot contain duplicates.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires an executable live smoke before a production-ready claim.
- Recent MCP hardening added request deadlines, strict JSON-RPC framing/response-ID validation, a 1,048,576-character frame cap, and a 16-frame pending stdout queue; the actual repository regression modules still need a runnable checkout.

## Recent completed work

### Cloud Run production safety bounds

- Bounded `STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS` to 1-600 seconds in runtime and deployment helper.
- Bounded checkpoint HMAC keys to 32-512 UTF-8 bytes and reject malformed boundary/control characters.
- Added focused Cloud Run entrypoint regressions.
- Updated Google Cloud deployment guidance to the Grafana MCP 1.4.1 baseline.

### Hermetic Cloud Run deploy-script regression

- Added `runtime/tests/test_deploy_cloud_run_script.py`.
- Uses a fake local `gcloud` and the real shell helper/identifier validator.
- Unsafe watchdog values must fail before any `gcloud` call.
- Valid values `1`, `17.5`, and `600` and the default `60` are serialization-checked.

## Run log — 2026-09-12 — independent telemetry comparator contract

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected the current repository metadata and reviewed:
- `scripts/deploy_cloud_run.sh`
- `runtime/tests/test_deploy_cloud_run_script.py`
- the runtime/test inventories
- `scripts/stageguard_doctor.py`
- `runtime/onboarding.py`
- `runtime/telemetry.py`
- `runtime/tests/test_telemetry.py`
- `runtime/investigator.py`
- `runtime/README.md`

All repository writes were limited to `UnknownGod2011/Grafana`. No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, or remediation provider was modified.

### Findings

1. The telemetry profile validated that affected and healthy bindings were non-empty, but it did not require the healthy comparator path to be independent from the affected path.
2. A profile could set `healthy_uplink == affected_uplink`. In that case the `healthy_peer_loss` contradiction query would read the same uplink as the causal query, defeating the intended independent-comparator semantics.
3. `healthy_peer_feeds` could include `affected_feed` or duplicate entries. That could make the healthy-peer dropped-frame aggregate self-referential or overweight one feed without any configuration failure.
4. `runtime/README.md` still described the old MCP 1.1.0 baseline and an obsolete implementation next step, so runtime documentation was no longer coherent with the executable repository.

### Exact changes made

#### 1. Enforced independent healthy comparator mappings

Commit: `b8dd30ec86c7d7bf2531948649a2c78050910395`

`runtime/telemetry.py` now rejects profiles where:
- `healthy_uplink` equals `affected_uplink`;
- `healthy_peer_feeds` contains `affected_feed`;
- `healthy_peer_feeds` contains duplicate feed bindings.

These checks happen during `TelemetryProfile` construction, so unsafe mappings fail before PromQL is generated or any incident investigation begins.

#### 2. Added focused telemetry regressions

Commit: `0787d2f12b1bc97f90bb538d20957a47cf353323`

`runtime/tests/test_telemetry.py` now covers all three new semantic invariants while preserving the existing custom-mapping, escaping, fixed-query-budget, recovery-window, and missing-evidence behavior.

#### 3. Reconciled stale runtime documentation

Commit: `a6aceddd03f48790e63b0485cdb5b80268a94487`

`runtime/README.md` now:
- describes the current `grafana/mcp-grafana:1.4.1` baseline;
- records server-side `--disable-write`, `--disable-proxied`, and `datasource,prometheus,loki` constraints;
- documents live registry `readOnlyHint=true` enforcement and bounded stdio behavior;
- documents the independent healthy-comparator mapping requirement;
- removes the obsolete MCP 1.1.0/early-remediation implementation narrative;
- sets the current validation priority to telemetry/MCP regression execution, MCP 1.4.1 live smoke, and the private Cloud Run metrics acceptance.

### Checks / results

- Authenticated GitHub inspection and all three repository writes succeeded.
- A fresh checkout/test attempt was made with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`; the execution environment again failed with `Could not resolve host: github.com` before repository tests could execute.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- An isolated Python proof of the exact new `TelemetryProfile` predicates succeeded: the default safe profile constructed successfully, and equal affected/healthy uplinks, affected-feed inclusion, and duplicate peer feeds were all rejected with the intended errors.
- Because the actual repository checkout is still unavailable, `python -m unittest runtime.tests.test_telemetry -v` has not yet been executed against the committed files. There is no new repository-suite green claim.

### Decisions

1. Treat healthy-peer evidence as an independent-comparator contract, not merely a naming convention.
2. Fail unsafe telemetry mappings at profile construction time rather than allowing diagnosis to run with self-referential evidence.
3. Preserve exact label-value semantics; the new validation rejects exact overlap/duplicates but does not silently normalize user label values.
4. Keep documentation aligned with the current MCP/runtime implementation rather than retaining historical hackathon-era version text.
5. Continue avoiding noisy GitHub Actions merely to work around the transient checkout/DNS failure.

### Blockers / unknowns

- `runtime.tests.test_telemetry` needs execution from an actual checkout.
- `runtime.tests.test_cloudrun_entrypoint` and `runtime.tests.test_deploy_cloud_run_script` still need a current repository run.
- `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins` still need an actual repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**When executable checkout is available, run `python -m unittest runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v` first. If clean, run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke; then proceed to the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
