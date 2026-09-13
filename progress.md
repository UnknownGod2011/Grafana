# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

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
- Local cooperative audit-lock sidecars must be owner-only, single-link regular files, may not be symbolic links, and the opened descriptor must match the exact file identity still visible at the sidecar path.
- Secure local audit data descriptors must name a single-link regular file that still matches the visible pathname; symbolic links, hard-link aliases, and path substitution fail closed.
- Anchored local JSONL audit reads/appends and local retention planning/execution use the shared secure descriptor primitive.
- Retention revalidates descriptor/path identity immediately before destructive pathname replacement and builds its recovery backup from the already-open authenticated source descriptor.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — Audit lock sidecar hard-link hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/incident_service.py`, `runtime/audit_file_lock.py`, `runtime/bootstrap.py`, the runtime test tree, and the current Git tree. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The shared secure audit data-file primitive already rejected multiple hard links, but the cooperative lock sidecar did not. A pre-existing hard-linked sidecar could therefore point at another regular file. `_open_lock_sidecar()` would accept the inode and then apply owner-only permissions with `fchmod`, mutating the peer file even though it was outside StageGuard's intended lock namespace. Because every anchored/retention/local audit operation acquires this sidecar, the gap belonged in the shared primitive rather than in one caller.

The planned base `JsonlAuditLog` migration remains the main local-demo gap. Closing the shared sidecar invariant first ensures every current and future caller inherits the same single-link ownership boundary.

### Exact changes made

1. Hardened `_open_lock_sidecar()` in `runtime/audit_file_lock.py` to require `st_nlink == 1` on the opened descriptor before any `fchmod` call.
2. Added the same single-link requirement to the visible-path `lstat()` recheck, alongside the existing regular-file, anti-symlink, and exact `(st_dev, st_ino)` identity checks.
3. Updated the sidecar function contract to explicitly describe it as owner-only and single-link.
4. Added `runtime/tests/test_audit_lock_hardlink_security.py` with regressions proving:
   - a hard-linked sidecar is rejected before lock acquisition;
   - the peer file bytes and permissions remain unchanged after rejection;
   - a normal sidecar remains a single-link regular file and is owner-only on POSIX.

Commits:
- `4551b5d93910928065b63d6b16b12018e5a300a0` — Reject hard-linked audit lock sidecars
- `3da57ee1d446158bcb21770e0c8cc2a8ed45e5ba` — Add audit lock hard-link security regressions

### Checks / results

- Authenticated GitHub connector inspection and writes succeeded on `UnknownGod2011/Grafana` `main`.
- Normal network checkout remains unavailable: `raw.githubusercontent.com` failed with `Could not resolve host`, consistent with the existing runner DNS blocker.
- I independently exercised the hardened lock logic locally without network dependencies. The hard-linked sidecar was rejected with the expected `multiple hard links` failure, the peer file content and `0644` permissions were unchanged, and a normal sidecar was created as a single-link regular file with `0600` permissions. Result: `focused audit lock hard-link checks: PASS`.
- The committed unittest file itself is not claimed green in a fresh repository checkout because the runner still cannot obtain the repository through normal Git/DNS.
- No GitHub Actions workflow was triggered merely to bypass the transient DNS failure.

### Decisions

1. StageGuard-owned lock sidecars must have exactly one directory entry, matching the existing audit data-file invariant.
2. Link-count validation must happen before `fchmod`; otherwise rejecting the sidecar afterward could still mutate an unrelated hard-linked peer.
3. The invariant belongs in the shared locking primitive so anchored audit, retention, and the upcoming base audit migration inherit it automatically.
4. This remains intentionally stricter than a generic file lock because local audit ownership and integrity are security boundaries.

### Blockers / unknowns

- Base `JsonlAuditLog` in `runtime/incident_service.py` still uses ordinary pathname opens and remains the main local-demo gap.
- Recent hard-link, retention, audit-chain, remediation, watchdog, Loki, investigator, MCP, Gemini, metrics-bridge, identity/auth/readiness/activation/onboarding/Cloud Run hardening suites still require a current executable checkout for consolidated regression execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Migrate the legacy/base `JsonlAuditLog` create/append/read/candidate paths in `runtime/incident_service.py` onto `audit_file_lock()` + `open_regular_audit_file()`, add legacy-log symlink/hard-link/path-swap regressions, then run the consolidated audit + retention suites as soon as executable checkout is restored.**
