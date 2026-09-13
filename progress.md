# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

This file is intentionally compact; detailed earlier run history remains in Git history.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Investigation and recovery accept only finite non-boolean numeric metric evidence; malformed samples become unavailable and can never prove diagnosis/recovery.
- Loki corroboration validates adapter envelopes, exact evidence windows, record budgets/shapes, scope, and event identity before corroborating a diagnosis.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state; its context/JSON boundary rejects malformed or non-finite evidence.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; remediation acceptance requires literal boolean `True`.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Cloud Logging and audit-chain JSON reject non-finite numeric state and malformed envelope values.
- Production remediation HTTP requests never follow redirects and do not redirect bearer/idempotency authority.
- Authentication/identity inputs are bounded and attacker-controlled credentials are bounded before comparison.
- Metric activation v2 pins the exact ordered eight-query profile contract; Loki activation v2 pins policy-owned LogQL/limit and bounded preflight evidence.
- Private Cloud Run metric requests reject redirects; the metrics bridge requires explicit non-loopback opt-in/authentication and bounded upstream waits.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; read-only/tool-surface restrictions are regression-locked.
- Core remediation watchdog clocks are finite native numbers; invalid/backward active clocks fail readiness closed.
- Local cooperative audit-lock sidecars must be owner-only regular files and may not be symbolic links; platforms with `O_NOFOLLOW` use it at open time.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from repository execution because the automation runner cannot resolve `github.com`; commits are not treated as passing tests.

## Recently completed work

- Metric/Loki activation, onboarding, API and CLI evidence failures are bounded/redacted and fail closed.
- `OperatorIdentity`, static bearer authentication, readiness policy, metrics bridge configuration, Cloud Run metrics acceptance, Grafana MCP smoke framing, remediation transport, Gemini evidence, audit documents/hash chains, investigator metrics, Loki corroboration, recovery verification, remediation acceptance, and execution watchdog clock handling have explicit defensive boundaries with focused regressions committed.
- Local audit locking now refuses symlink/directory substitution for the sidecar used by anchored JSONL writes and retention coordination.

## Run log — 2026-09-13 — Local audit lock sidecar integrity

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata and the current runtime tree, then reviewed `runtime/incident_service.py`, `runtime/anchored_incident_service.py`, `runtime/audit_integrity.py`, `runtime/audit_anchor.py`, `runtime/audit_file_lock.py`, `runtime/cloud_audit.py`, `runtime/tests/test_audit_file_lock.py`, and `runtime/tests/test_anchored_transition_failure_authority.py`. Also attempted a fresh executable checkout before implementation. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or triggered.

### Finding

`audit_file_lock()` derived a sidecar path from the local audit path and opened it with ordinary `os.open(..., O_CREAT)` semantics. A pre-created symbolic link at that sidecar path could therefore redirect StageGuard's permission change and cross-process lock operations onto an unrelated file. A non-regular filesystem object was also not explicitly rejected. This affects the local anchored JSONL/retention coordination path rather than Cloud Logging, but it is still part of the operator-safe audit integrity boundary.

### Exact changes made

1. Added `_open_lock_sidecar()` in `runtime/audit_file_lock.py`.
2. Reject a sidecar already identifiable as a symbolic link before opening it.
3. Add `O_NOFOLLOW` when the host Python/platform exposes it, closing the open-time symlink race on supporting POSIX systems.
4. Validate the opened descriptor with `fstat()` and require a regular file before any lock operation.
5. Preserve the owner-only `0600` mode enforcement and Windows compatibility behavior.
6. Ensure the descriptor is closed on every validation failure.
7. Added `runtime/tests/test_audit_file_lock_security.py` covering directory substitution, symlink redirection without touching the symlink target, and ordinary owner-only regular-sidecar creation.

Commits:
- `a388f3a1e6294ee7db7b4e56363d2b681d8c1b35` — Harden local audit lock sidecar handling
- `6b8f425dc9757533306a0f0d755f4ee11049e817` — Add audit lock sidecar security regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Fresh repository checkout still failed before tests with `Could not resolve host: github.com`; no GitHub Actions workflow was triggered merely to bypass that transient runner failure.
- Independently compiled the hardened lock module successfully with `py_compile` in the execution environment.
- Independently exercised the critical behavior on Linux: a symlink sidecar was rejected with `audit lock sidecar must not be a symbolic link`, its target content remained unchanged, and a normal sidecar was created as a regular file with mode `0600`.
- The repository-level new pytest file is therefore not yet claimed green against the real checkout/dependency set.

### Decisions

1. The local audit sidecar is security-sensitive because both anchored append/read and retention coordination trust the lock to serialize lifecycle/audit mutation.
2. `O_NOFOLLOW` is used where available, but descriptor-type validation remains mandatory because platform capability varies.
3. Unsafe sidecar state fails closed with a StageGuard-owned `RuntimeError` rather than attempting replacement/deletion of an operator filesystem object.
4. No automatic cleanup of a suspicious sidecar is performed; destructive filesystem repair must remain an explicit operator action.

### Blockers / unknowns

- `runtime.tests.test_audit_file_lock_security` and the existing lock/anchored-retention suites still need a current executable repository checkout.
- Recent remediation, audit, MCP, Gemini, metrics-bridge, watchdog, identity/auth/readiness/activation/onboarding/Cloud Run/investigator/Loki hardening suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, first run `PYTHONPATH=runtime python -m pytest runtime/tests/test_audit_file_lock.py runtime/tests/test_audit_file_lock_security.py runtime/tests/test_anchored_transition_failure_authority.py -q` and fix any failure immediately. If clean, run the accumulated watchdog/remediation/Loki/investigator/MCP/audit/Gemini/auth/readiness/bridge/activation suites, then the live pinned Grafana MCP 1.4.1 smoke before the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
