# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, explicit no-replay reconciliation for post-remediation persistence uncertainty, and versioned telemetry onboarding/preflight.

Core invariants retained:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Durable checkpoint/audit failures fail closed and uncommitted state is not operator-visible lifecycle authority.
- Once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Browser/API surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Expected evidence transport/protocol/datasource failures cross runtime boundaries as `EvidenceUnavailable`; provider exception text is diagnostic-only and must not be copied into operator/onboarding results.
- Unexpected programming/policy exceptions must fail loudly rather than being downgraded to telemetry unavailability.
- Telemetry onboarding never treats NaN or infinities as successful evidence, and activation independently requires every `ok` slot to contain a finite numeric sample with no error detail.
- Telemetry activation v2 pins the exact profile-derived phase/name/PromQL contract in deterministic order and hashes the normalized observed samples; arbitrary successful-looking eight-slot preflights cannot be activated.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- Runtime metric readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.
- A metrics bridge bound beyond loopback requires explicit network-bind opt-in, inbound bearer authentication, strict bearer-token syntax, and a minimum 32-character credential.
- The private Cloud Run acceptance harness now requires one bounded selector-safe Prometheus job identity before any upstream or Docker action; the same validated identity is used in generated YAML and exact PromQL selectors.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; server-side write/proxy restrictions are regression-locked; the live smoke rejects any advertised MCP tool that is not explicitly annotated `readOnlyHint=true`.
- Grafana MCP smoke requests are time-bounded, stdout JSON-RPC frames are individually bounded, strict framing/response integrity fails closed, and pending stdout frames are held in a fixed-capacity queue.
- Cloud Run remediation/recovery execution watchdog configuration is bounded to 1-600 seconds.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject leading/trailing whitespace or control characters before runtime composition.
- The Cloud Run deployment helper has a hermetic shell regression boundary that rejects unsafe watchdog values before any `gcloud` invocation.
- Telemetry profiles require independent healthy comparators: `healthy_uplink` cannot equal `affected_uplink`, `healthy_peer_feeds` cannot include the affected feed, and healthy peer feeds cannot contain duplicates.

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
- Added focused Cloud Run entrypoint and hermetic deploy-script regressions.

### Telemetry mapping, onboarding, and activation safety
- Enforced independent healthy comparator mappings.
- Reconciled runtime documentation with the Grafana MCP 1.4.1 baseline and current safety controls.
- Hardened onboarding to catch only `EvidenceUnavailable`, redact provider detail from operator-visible preflight state, and fail unexpected programming/policy exceptions loudly.
- Refused NaN/infinite telemetry samples during preflight and independently revalidated finite numeric `ok` samples at the activation boundary.
- Activation v2 now verifies the exact ordered profile-derived preflight contract and includes normalized observed sample values in the slot digest; legacy v1 activation records are deliberately refused so operators rerun preflight under the stronger contract.

## Run log — 2026-09-12 — exact telemetry activation contract boundary

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected repository metadata and reviewed:
- `runtime/activation.py`
- `runtime/tests/test_activation.py`
- `runtime/onboarding.py`
- `runtime/telemetry.py`
- `runtime/evidence_errors.py`
- `README.md` activation/onboarding description

No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, IAM binding, or remediation provider was modified.

### Findings

1. The prior activation boundary validated `ready=True`, exactly eight slots, successful statuses, finite numeric samples, and no error detail, but it did not prove that those eight slots were the semantic queries generated from the telemetry profile.
2. A caller able to construct `PreflightResult` directly could therefore supply eight arbitrary `phase/name/promql` entries such as `vector(...)`, mark them `ok`, and obtain an activation record for an unrelated real profile as long as the production ID matched.
3. The activation `slot_digest_sha256` hashed phase/name/PromQL/status but omitted the actual observed sample values, so two successful preflights with different telemetry observations produced the same evidence digest.
4. Strengthening digest semantics without a schema/version transition would leave existing v1 records accepted under weaker assumptions, so a version bump is the safer fail-closed migration.

### Exact changes made

#### 1. Exact profile-derived activation contract validation

Commit: `f099657b40d914f25f526240262efa3049f22d74`

`runtime/activation.py` now:
- imports the canonical `investigation_queries()` and `recovery_queries()` builders;
- derives the exact eight-slot expected contract as ordered `(phase, name, promql)` tuples from the supplied `TelemetryProfile`;
- requires the supplied successful preflight to match that complete ordered contract before activation;
- rejects arbitrary queries, renamed slots, wrong phases, omissions/additions, and reordered slots even when every entry claims `status="ok"` with a finite value;
- normalizes every accepted observed sample through `float(...)` and includes it in `slot_digest_sha256`, binding the activation evidence digest to what the read-only evidence plane actually returned;
- bumps `ACTIVATION_VERSION` from 1 to 2 so weaker legacy activation records fail closed and require a fresh telemetry preflight.

#### 2. Added activation forgery and migration regressions

Commit: `9c08b776bc51ac7a21540217e979275d0f9ffd53`

`runtime/tests/test_activation.py` now:
- keeps numeric/non-finite/detail forgery tests aligned with the real profile-derived query contract so each regression reaches the intended validation boundary;
- rejects eight arbitrary successful-looking `vector(...)` slots;
- rejects a reversed ordering of otherwise legitimate real preflight slots;
- proves different observed sample values generate different activation slot digests;
- verifies activation records use the current version and that a legacy version is rejected at verification;
- retains profile-change, datasource-change, expiry, round-trip, unactivated-service, and matching-activation coverage.

### Checks / results

- Authenticated GitHub inspection and both code/test writes succeeded.
- A fresh executable checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`.
- The runner again failed before checkout with `Could not resolve host: github.com`; therefore `python -m unittest runtime.tests.test_activation -v` could not execute against the committed tree.
- No GitHub Actions workflow was triggered or rerun merely to bypass the transient runner DNS failure.
- There is no new green-suite claim for this change yet.

### Decisions

1. Treat the exact semantic telemetry query contract as part of activation authority, not merely the count/status/value shape of preflight output.
2. Require deterministic slot ordering because the official onboarding path already generates a deterministic eight-slot sequence, and ordering makes the pinned evidence digest stable and reviewable.
3. Bind observed finite sample values into the digest so an activation record distinguishes materially different successful evidence snapshots.
4. Bump the activation schema to v2 and intentionally reject v1 instead of silently accepting weaker historical pins; this forces a safe one-time preflight refresh for existing deployments.
5. Keep Grafana/MCP read-only and make no changes to remediation credentials or write paths.
6. Continue avoiding noisy GitHub Actions solely to work around the transient checkout DNS failure.

### Blockers / unknowns

- `runtime.tests.test_activation` requires execution from an actual checkout after the v2 change.
- Existing deployments carrying `stageguard` metric activation v1 files must rerun telemetry preflight to generate v2 records; this is intentional fail-closed migration behavior.
- `runtime.tests.test_onboarding`, `runtime.tests.test_cloud_run_metrics_acceptance`, `runtime.tests.test_telemetry`, `runtime.tests.test_cloudrun_entrypoint`, and `runtime.tests.test_deploy_cloud_run_script` still need a current repository run.
- `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins` still need an actual repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- The strengthened Cloud Run bridge set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Run log — 2026-09-12 — private acceptance job identity boundary

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected repository metadata and reviewed:
- `runtime/cloud_run_metrics_acceptance.py`
- `runtime/cloud_run_metrics_bridge.py`
- `runtime/tests/test_cloud_run_metrics_acceptance.py`
- current runtime/test directory structure

No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, IAM binding, or remediation provider was modified.

### Findings

1. The private Cloud Run acceptance harness uses one Prometheus `job_name` in two security-sensitive syntactic contexts: generated Prometheus YAML and an exact PromQL label selector.
2. `run_acceptance(..., job_name=...)` previously accepted arbitrary strings. A quote/newline or selector-shaped value could make the generated config malformed or alter the query selector, weakening the meaning of the `up -> down -> up` proof.
3. The harness already rejects ambiguous Prometheus result sets, so validating the identity before building YAML/PromQL is the missing complement: the proof should have exactly one syntactically unambiguous target identity from the start.

### Exact changes made

#### 1. Hardened Prometheus acceptance job identity

Commit: `e5f9b8bcbba124b41febe6123f4c17e8c6ce9215`

`runtime/cloud_run_metrics_acceptance.py` now:
- defines `MAX_JOB_NAME_LENGTH = 128`;
- adds `normalize_job_name()` with a deliberately narrow `A-Za-z0-9_.:-` alphabet and an alphanumeric first character;
- rejects empty, boundary-whitespace, overlong, newline/space/quote, and selector-shaped job names;
- validates `job_name` at the very start of `run_acceptance()`, before target/network checks and before Docker;
- revalidates at the YAML and PromQL construction boundaries as defense in depth;
- serializes the validated YAML job name as a JSON string, which is also a valid YAML scalar.

#### 2. Added focused regression coverage

Commit: `7c84133f0e540564e62ffea51cb0c8e437c28638`

`runtime/tests/test_cloud_run_metrics_acceptance.py` now verifies:
- valid production-style job names and the 128-character boundary are accepted;
- blank, whitespace-padded, whitespace-containing, newline-containing, quote/PromQL-injection-shaped, invalid-leading-character, and overlong names are rejected;
- an invalid job name fails before unauthenticated Cloud Run probing and before Docker preflight;
- generated Prometheus configuration uses the validated quoted job identity;
- all pre-existing up/down/up, ambiguity, credential-redaction, Docker isolation, upstream recheck-order, and CLI-sanitization tests remain represented.

### Checks / results

- Authenticated GitHub inspection and all three repository writes succeeded.
- A fresh executable checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`; the runner again failed with `Could not resolve host: github.com` before repository tests could execute.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- Because the runner cannot obtain an executable checkout, `python -m unittest runtime.tests.test_cloud_run_metrics_acceptance -v` has not yet been executed against the committed tree. There is no new repository-suite green claim.

### Decisions

1. Treat the Prometheus job name as part of the acceptance proof's security/correctness contract, not as arbitrary presentation text.
2. Prefer a narrow allowlist over PromQL escaping because StageGuard controls the reference acceptance identity and does not need arbitrary Unicode/job labels for this proof.
3. Fail before any Cloud Run or Docker interaction when the identity is invalid, preserving the harness's non-destructive behavior.
4. Keep the existing exact-one-result Prometheus requirement; job-name validation narrows construction, while exact-one-result validation protects runtime observation.
5. Continue avoiding noisy GitHub Actions solely to work around the transient runner DNS failure.

### Blockers / unknowns

- `runtime.tests.test_cloud_run_metrics_acceptance` needs execution from an actual checkout after this change.
- `runtime.tests.test_onboarding`, `runtime.tests.test_telemetry`, `runtime.tests.test_cloudrun_entrypoint`, and `runtime.tests.test_deploy_cloud_run_script` still need a current repository run.
- `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins` still need an actual repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Run log — 2026-09-12 — finite telemetry activation boundary

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected repository metadata and reviewed:
- `runtime/onboarding.py`
- `runtime/activation.py`
- `runtime/tests/test_onboarding.py`
- `runtime/tests/test_activation.py`
- `runtime/cloud_run_metrics_acceptance.py`
- `runtime/cloud_run_metrics_bridge.py`
- runtime/test directory structure

No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, IAM binding, or remediation provider was modified.

### Findings

1. `preflight_telemetry()` treated every non-`None` adapter result as an `ok` sample after `float(value)`. Prometheus can represent `NaN`, `+Inf`, and `-Inf`, so an unusable semantic measurement could incorrectly satisfy onboarding readiness.
2. The same coercion silently accepted adapter contract violations such as `True` or the string `"1.0"`, which can hide programming/integration defects instead of failing loudly.
3. `create_activation_record()` trusted `PreflightResult.ready` plus eight `status == "ok"` slots without independently validating the slot values. A malformed or manually constructed preflight could therefore be pinned despite missing/non-finite values or attached error detail.

### Exact changes made

#### 1. Refused non-finite telemetry during onboarding

Commit: `04356574bd3598569be831bb912b388384993465`

`runtime/onboarding.py` now:
- accepts finite `int`/`float` samples only;
- explicitly rejects booleans and nonnumeric adapter return types with `TypeError`, preserving the fail-loud programming-contract invariant;
- maps `NaN` and infinities to a non-ready `status="invalid"` slot;
- stores `value=None` for invalid samples so operator-visible JSON never contains non-standard JSON `NaN`/`Infinity` values;
- retains the generic `query returned a non-finite sample` detail without provider text.

#### 2. Added onboarding regressions

Commit: `43833872e5f98f8b7c29d9b0ba74a113ed47e1ee`

`runtime/tests/test_onboarding.py` now verifies:
- `NaN`, `+Inf`, and `-Inf` all refuse readiness while the remaining bounded slots are still checked;
- invalid samples are serialized with `allow_nan=False` and do not leak `NaN`/`Infinity` tokens;
- boolean, string, and arbitrary-object adapter returns fail loudly rather than being coerced;
- existing missing-sample, evidence-redaction, and unexpected-exception behavior remains covered.

#### 3. Revalidated successful evidence at activation

Commit: `0b39c57d047b4c2a164dbb4eca87586b538ad88d`

`runtime/activation.py` now has an independent `_validate_successful_preflight()` boundary that requires:
- `ready=True`;
- exactly eight slots;
- every slot status to be `ok`;
- every `ok` value to be numeric, non-boolean, and finite;
- every `ok` slot to carry no error/detail text.

This prevents activation from relying solely on a caller-controlled status flag and keeps the production pinning boundary fail-closed even if a malformed `PreflightResult` is constructed outside the normal onboarding function.

#### 4. Added activation-forgery regressions

Commit: `db47909d34bcdf1a0b0ce6892d1d8bf8399ff8b8`

`runtime/tests/test_activation.py` now constructs deliberately forged ready/ok preflights and verifies activation rejects:
- `None`, boolean, and string slot values;
- `NaN`, `+Inf`, and `-Inf` slot values;
- `ok` slots that still contain error detail.

### Checks / results

- Authenticated GitHub reads and all repository writes succeeded.
- A fresh executable checkout was attempted again with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`; the runner failed with `Could not resolve host: github.com` before tests could execute.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- Because the runner cannot obtain an executable checkout, the changed onboarding/activation modules are not claimed green yet.

### Decisions

1. Treat finite numeric telemetry as part of the activation trust boundary, not merely a presentation/data-quality concern.
2. Mark Prometheus non-finite values as operationally invalid evidence so all eight preflight checks still complete and operators can see which semantic slot is unusable.
3. Treat adapter type violations as programming/integration errors and fail loudly instead of normalizing them into ordinary evidence loss.
4. Revalidate the complete successful-preflight shape at activation so downstream safety does not depend on `PreflightResult.ready` being trustworthy by construction.
5. Continue avoiding noisy GitHub Actions solely to work around the transient runner DNS failure.

### Blockers / unknowns

- `runtime.tests.test_onboarding` and `runtime.tests.test_activation` require execution from an actual checkout after these changes.
- The previously pending Cloud Run acceptance/onboarding/telemetry/entrypoint/deploy-script combined set still requires a current repository run.
- MCP timeout/surface/image-pin regressions and a live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remain required.
- The private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance still requires external credentials/service state and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**When executable checkout is available, run `python -m unittest runtime.tests.test_activation runtime.tests.test_onboarding runtime.tests.test_cloud_run_metrics_acceptance runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v` first. If clean, update any operator/onboarding documentation that needs an explicit v1→v2 activation refresh note, then run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke; finally proceed to the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
