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
- Cloud Logging and audit-chain canonicalization reject non-finite numeric state and malformed/bounded envelope identifiers.
- Production remediation HTTP requests never follow redirects and do not redirect bearer/idempotency authority.
- Authentication/identity inputs are bounded and attacker-controlled credentials are bounded before comparison.
- Metric activation v2 pins the exact ordered eight-query profile contract; Loki activation v2 pins policy-owned LogQL/limit and bounded preflight evidence.
- Private Cloud Run metric requests reject redirects; the metrics bridge requires explicit non-loopback opt-in/authentication and bounded upstream waits.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; read-only/tool-surface restrictions are regression-locked.
- Core remediation watchdog clocks are finite native numbers; invalid/backward active clocks fail readiness closed.
- Local cooperative audit-lock sidecars must be owner-only regular files, may not be symbolic links, and the opened descriptor must match the exact file identity still visible at the sidecar path.
- The anchored local JSONL audit data file now uses the same no-follow, regular-file, descriptor/path-identity discipline before create/read/append and forbids truncating opens at the secure primitive.

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
- Audit-chain canonicalization enforces the same incident/event/actor envelope byte limits and ASCII-control rejection as durable Cloud Logging.
- Local audit locking rejects symlink/directory substitution and verifies post-open descriptor/path identity.
- Anchored local JSONL audit creation, reads, candidate reads, and appends now use a shared secure descriptor opener rather than ordinary pathname opens.

## Run log — 2026-09-13 — Audit JSONL data-file path hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata/tree, `runtime/audit_file_lock.py`, `runtime/incident_service.py`, `runtime/anchored_incident_service.py`, `runtime/retention_executor.py`, and the existing audit lock regressions. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The cooperative lock sidecar already rejected symlinks and post-open path identity substitution, but the actual local audit JSONL path did not share that protection. `JsonlAuditLog` and the anchored reader still used ordinary `os.open()`/`Path.open()` calls. A path replaced by a symlink could therefore redirect audit reads or appends even though the sidecar lock itself was safe. Retention code also still contains ordinary pathname opens and remains a follow-up surface.

### Exact changes made

1. Added `open_regular_audit_file()` in `runtime/audit_file_lock.py` as a shared secure local audit-data opener.
2. The helper rejects a visible symlink, adds `O_NOFOLLOW` when supported, validates the opened descriptor as a regular file, post-validates the visible path with `lstat()`, and requires descriptor/path `(st_dev, st_ino)` identity before returning the descriptor.
3. The helper explicitly rejects `O_TRUNC`; on platforms without `O_NOFOLLOW`, truncating a substituted target could otherwise occur before post-open validation.
4. The helper maintains owner-only `0600` intent where `fchmod` is available and closes descriptors on every validation failure.
5. `AnchoredJsonlAuditLog` now overrides initialization, append, read, and anchored candidate read so create/read/append operations use validated descriptors while remaining under the existing cooperative lock.
6. Added `runtime/tests/test_audit_data_file_security.py` covering symlink rejection without target mutation, simulated post-open identity substitution, `O_TRUNC` refusal, constructor/append/read path replacement, normal round-trip behavior, and regular owner-only file creation.

Commits:
- `189bf738b4d2a8a4995569e02b352b7895caadbf` — Harden local audit data file opens
- `538d017ce5c187d5441cdbf6380ea3ea527d36bd` — Use secure audit data file descriptors
- `fa50b3a8def6e3e4917625cb65dbdffe092cb324` — Add audit data file security regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and all implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- A fresh clone/remote probe was attempted before and after implementation; the execution environment still fails with `Could not resolve host: github.com`.
- Because executable checkout remains unavailable, `runtime/tests/test_audit_data_file_security.py` and related audit suites are not claimed green in this run.
- No GitHub Actions workflow was triggered merely to bypass the transient DNS failure.

### Decisions

1. Data-file safety must bind the opened descriptor to the exact visible regular file, not merely trust the cooperative sidecar lock.
2. `O_TRUNC` is forbidden in the shared primitive because post-open identity checks cannot undo truncation if a platform followed a substituted path before validation.
3. This run integrates the primitive into the anchored local audit implementation, which is the anchor-aware path used by the current StageGuard local integrity design. The older base `JsonlAuditLog` and retention scan/execution pathname opens remain explicit follow-up surfaces rather than being silently treated as hardened.

### Blockers / unknowns

- The new audit data-file regressions still need a current executable repository checkout.
- Base `JsonlAuditLog` in `incident_service.py` still uses ordinary pathname opens and should be migrated to the secure primitive to remove the legacy/local-demo gap.
- `retention_executor.py` and retention planning still perform ordinary audit-path opens/stat calls; those should be migrated to the same descriptor-identity discipline so compaction cannot reopen a substituted path.
- Recent audit-chain, remediation, watchdog, Loki, investigator, MCP, Gemini, metrics-bridge, identity/auth/readiness/activation/onboarding/Cloud Run hardening suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Migrate the base `JsonlAuditLog` plus retention planner/executor audit-file reads to `open_regular_audit_file()` (or an equivalent descriptor-bound wrapper), add substitution regressions around retention prepare/execute, then run the focused audit/retention suites as soon as executable checkout works.**
