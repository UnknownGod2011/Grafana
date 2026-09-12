# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, explicit no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

This file was compacted on 2026-09-13 to keep the handoff actionable. Detailed prior run history remains preserved in Git history.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Durable checkpoint/audit failures fail closed and uncommitted state is not operator-visible lifecycle authority.
- Once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Browser/API/onboarding surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Expected evidence transport/protocol/datasource failures cross runtime boundaries as `EvidenceUnavailable`; unexpected programming/policy exceptions fail loudly.
- Metric and Loki activation records are bounded, schema/version validated, expiry constrained, datasource/contract pinned, and rejected when malformed.
- Telemetry activation v2 pins the exact profile-derived ordered eight-query contract and normalized observed samples.
- Loki activation v2 requires the exact policy-owned LogQL/limit contract and a bounded successful preflight with no error detail.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- Runtime metric readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.
- A metrics bridge bound beyond loopback requires explicit network-bind opt-in, inbound bearer authentication, strict bearer-token syntax, and a minimum 32-character credential.
- The private Cloud Run acceptance harness uses one bounded selector-safe Prometheus job identity consistently in YAML and PromQL.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; server-side write/proxy restrictions and live `readOnlyHint=true` validation are regression-locked.
- Grafana MCP smoke requests are time-bounded; stdout JSON-RPC frames and pending-frame queue growth are bounded and framing/response integrity fails closed.
- Cloud Run remediation/recovery execution watchdog configuration is bounded to 1-600 seconds.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject boundary whitespace/control characters.
- Telemetry profiles require independent healthy comparators.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke before a production-ready claim.
- Recent MCP hardening added request deadlines, strict JSON-RPC framing/response-ID validation, a 1,048,576-character frame cap, and a 16-frame pending stdout queue; current repository regressions still need a runnable checkout.

## Recently completed work

### Metric onboarding / activation

- Enforced independent healthy comparator mappings.
- Onboarding catches only `EvidenceUnavailable`, redacts provider detail, rejects non-finite samples, and fails unexpected programming/policy exceptions loudly.
- Metric activation v2 verifies the exact ordered profile-derived preflight contract and hashes normalized observed sample values.
- `runtime/activation.py` now independently validates every persisted or manually constructed activation authority object:
  - canonical lowercase 64-character SHA-256 digests;
  - non-empty trimmed production identity;
  - integer non-negative creation/expiry timestamps;
  - expiry strictly after creation;
  - lifetime capped at seven days;
  - explicit test clocks must be non-negative integers;
  - write/load/verify all re-run the shape validation.
- New activation regressions cover malformed digests, invalid timestamp relationships, excessive lifetime, malformed production identity, invalid explicit clocks, arbitrary PromQL forgery, reordered slots, non-finite values, legacy version rejection, and evidence-value digest binding.

Commits:
- `dfe6a5cf5164aa1553d6b146487ff7517dc6294d` — Harden telemetry activation record validation
- `4e6e3264e88ef19c80de7e522544273cf52ff0d4` — Add activation record integrity regressions

### Loki onboarding / activation

- `preflight_loki()` now catches only `EvidenceUnavailable` and emits a stable `evidence source unavailable` detail; provider exception text is no longer serialized into preflight output.
- Unexpected programming/policy exceptions now propagate instead of being mislabeled as evidence unavailability.
- Loki activation is upgraded from v1 to v2. Existing v1 files intentionally fail closed and must be regenerated by rerunning preflight.
- Successful Loki activation now independently requires:
  - `ready=True`, `status="ok"`, and no truncation;
  - no error/detail text on a successful preflight;
  - exact policy-owned LogQL and bounded line limit;
  - line count within the query bound;
  - bounded non-empty start/end metadata without control characters.
- The Loki preflight digest now includes `line_count` in addition to production/query/window/limit/status/truncation.
- Persisted/manual Loki activation records now receive the same canonical SHA-256, production-id, timestamp, lifetime, and explicit-clock validation as metric activation records.
- New regressions cover secret-bearing evidence failures, unexpected programming errors, forged successful preflights, line-count/window abuse, malformed digests, invalid lifetimes, write-time revalidation, invalid clocks, and v1 rejection.

Commits:
- `09b7a9e52e290cfd7b4c4113374aaa7388d47fb6` — Harden Loki preflight and activation authority
- `abddb80c002041024d5cfa0cdd4acc12a2e61c0f` — Add Loki activation safety regressions

### Cloud Run / MCP safety already retained

- Cloud Run execution watchdog: 1-600 seconds in runtime and deployment helper.
- Checkpoint HMAC key: 32-512 UTF-8 bytes with whitespace/control rejection.
- Hermetic deploy-script regression prevents invalid watchdog values from reaching `gcloud`.
- Private metrics acceptance job identity is allowlisted and bounded before any Cloud Run/Docker action.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image pin regressions.

## Run log — 2026-09-13 — activation authority parity hardening

### Inspected at start

Read the complete pre-compaction `progress.md` before deciding what to change. Inspected repository metadata and reviewed:
- `runtime/activation.py`
- `runtime/tests/test_activation.py`
- `runtime/bootstrap.py`
- `runtime/incident_service.py`
- `runtime/log_activation.py`
- `runtime/tests/test_log_activation.py`
- `runtime/log_evidence.py`
- `runtime/mcp_log_client.py`
- `runtime/evidence_errors.py`
- relevant README onboarding/activation material

No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, IAM binding, or remediation provider was modified.

### Findings

1. Metric activation v2 already pinned exact semantic evidence, but persisted records still accepted malformed digest text, inconsistent timestamp relationships, or lifetimes longer than the constructor would create if they were manually constructed or edited.
2. `create_activation_record()` and `verify_activation_record()` coerced explicit test clocks with `int(...)`, which allowed booleans/floats/strings to cross a boundary intended to be integer Unix time.
3. Loki onboarding lagged behind metric onboarding: `preflight_loki()` caught every exception and serialized exception type/message, so provider URLs/tokens or backend details could leak into operator-visible preflight output while programming defects were hidden as ordinary datasource errors.
4. Loki activation v1 validated only part of the successful preflight shape and had much weaker persisted-record validation than metric activation.

### Exact changes made

#### Metric activation persisted-authority validation

`runtime/activation.py` now centralizes `_validate_record_shape()` and applies it during create, write, load, and verify. Canonical SHA-256 encoding, production identity, timestamp ordering, seven-day maximum lifetime, and explicit integer clock semantics are all independently enforced.

`runtime/tests/test_activation.py` adds focused regressions for each new fail-closed boundary.

#### Loki onboarding redaction and fail-loud behavior

`preflight_loki()` now catches only `EvidenceUnavailable` and emits the stable generic detail `evidence source unavailable`. Any unexpected exception propagates.

#### Loki activation v2

`runtime/log_activation.py` now validates the full successful preflight shape, includes `line_count` in its preflight digest, validates bounded window metadata, applies canonical persisted-record validation across create/write/load/verify, and rejects legacy v1 records.

`runtime/tests/test_log_activation.py` adds provider-secret redaction, unexpected-exception, forged-preflight, digest/timestamp/lifetime, clock, and v1 migration regressions.

### Checks / results

- Authenticated GitHub reads/writes succeeded for all four code/test commits.
- Latest commits were confirmed on `UnknownGod2011/Grafana` main.
- A fresh executable checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`.
- The runner still failed before checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered or rerun merely to bypass the transient DNS failure.
- Therefore the newly committed metric/Loki activation regression modules are **not yet claimed green**.

### Decisions

1. Treat loaded activation files as persisted authority, not trusted constructor output; validate them independently at every boundary.
2. Keep activation lifetime semantics identical whether a record is created normally, loaded from disk, or manually instantiated in code.
3. Bring Loki preflight onto the same `EvidenceUnavailable` redaction contract as Prometheus onboarding.
4. Bump Loki activation to v2 rather than silently accepting weaker v1 records; operators must rerun preflight once.
5. Keep Grafana/MCP read-only and do not add remediation/write credentials to onboarding.
6. Avoid noisy GitHub Actions solely to work around runner DNS.

### Blockers / unknowns

- `runtime.tests.test_activation` and `runtime.tests.test_log_activation` need execution from an actual checkout after these changes.
- Existing Loki activation v1 files must be regenerated with `runtime/preflight.py`; this is intentional fail-closed migration behavior.
- Metric activation v1 files already require the same v2 refresh.
- `runtime.tests.test_onboarding`, `runtime.tests.test_cloud_run_metrics_acceptance`, `runtime.tests.test_telemetry`, `runtime.tests.test_cloudrun_entrypoint`, and `runtime.tests.test_deploy_cloud_run_script` still need a current repository run.
- `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins` still need an actual repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The strengthened Cloud Run bridge set and execution-reconciliation/operator/Playwright safety set still need current execution.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, run `python -m unittest runtime.tests.test_activation runtime.tests.test_log_activation runtime.tests.test_onboarding runtime.tests.test_cloud_run_metrics_acceptance runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v`. Fix any regressions before changing another production boundary. If clean, run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke, then proceed to the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
