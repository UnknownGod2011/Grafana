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
- Base and anchored local JSONL audit create/read/append paths use the shared secure descriptor primitive under the cooperative audit lock.
- Local JSONL audit reads and appends revalidate descriptor/path identity during the operation so post-open path replacement cannot silently redirect or conceal audit I/O.
- Retention planning/execution uses the shared secure descriptor primitive, revalidates descriptor/path identity immediately before destructive pathname replacement, and builds recovery backups from the already-open authenticated source descriptor.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — Base JsonlAuditLog descriptor-bound migration

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the current repository metadata, `runtime/incident_service.py`, `runtime/audit_file_lock.py`, and the new audit security regression surface. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The base `JsonlAuditLog` in `runtime/incident_service.py` was the remaining local audit implementation using ordinary pathname opens. Its constructor used `os.open()` directly, append reopened the path directly, and `read()` / `read_candidates()` used `Path.open()`. That left the local/demo audit path outside the symlink, hard-link, exact-inode, and cooperative-lock guarantees already applied to anchored audit and retention.

There was also a post-open integrity concern: validating only when a descriptor is first opened does not prove that the pathname still names the same inode while the operation is in progress. For audit append/read semantics, a post-open path replacement must be detected rather than allowing bytes to be written to an orphaned inode or evidence to be read from a file no longer reachable through the configured audit path.

### Exact changes made

1. Migrated `JsonlAuditLog.__init__()` onto `audit_file_lock()` + `open_regular_audit_file()`.
2. Migrated `append()` onto the same cooperative lock and secure descriptor primitive; descriptor/path identity is checked before the write and again after `fsync()`.
3. Migrated `read()` and `read_candidates()` from `Path.open()` to validated read-only file descriptors wrapped with `os.fdopen(..., closefd=False)` while the cooperative lock is held.
4. Added before/after descriptor/path identity checks around reads so a pathname swap during evidence consumption fails closed.
5. Added `runtime/tests/test_jsonl_audit_file_security.py` covering:
   - symlinked audit-path rejection without target mutation;
   - hard-linked audit-path rejection without peer mutation;
   - post-open append path replacement rejected before audit bytes are written;
   - post-open read path replacement rejected;
   - normal append/read/candidate round-trip and owner-only/single-link invariants.

Commits:
- `7ba4fa665a9ee5e76f74522066bca7a04fc17259` — Harden base JSONL audit file access
- `fdedd207f84e06d6d5efcc58c485e0217644e0fc` — Add base JSONL audit file security regressions

### Checks / results

- Authenticated GitHub connector inspection and writes succeeded on `UnknownGod2011/Grafana` `main`.
- The exact commit diff for `7ba4fa6` was inspected and contains only the intended import plus `JsonlAuditLog` migration hunks; no unrelated `IncidentService` logic changed.
- Normal network checkout remains unavailable: `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` failed with `Could not resolve host: github.com`, consistent with the existing runner DNS blocker.
- Independently exercised the migrated lock/descriptor logic locally without network dependencies. Normal append/read/candidate round-trip passed, hard-link aliasing was rejected, and a path swapped after secure open was rejected before append mutated the displaced original. Result: `focused JsonlAuditLog security checks: PASS`.
- The committed repository unittest file itself is not claimed green in a fresh checkout because the runner still cannot obtain the repository through normal Git/DNS.
- No GitHub Actions workflow was triggered merely to bypass the transient DNS failure.

### Decisions

1. All local JSONL audit implementations should share one filesystem integrity model rather than maintaining separate ad hoc pathname-I/O behavior.
2. Cooperative locking protects legitimate concurrent StageGuard processes; secure descriptor identity validation protects against filesystem alias/substitution hazards. Both are required.
3. Append revalidates identity after durable `fsync()` so a path replacement that occurs during the write is surfaced as an integrity failure rather than reported as a successful audit append.
4. Reads revalidate identity after evidence consumption so data read from an inode that ceased to be the configured audit file during the operation cannot silently become trusted lifecycle evidence.
5. No GitHub Actions run is justified while the local runner DNS failure remains the only reason the new focused suite cannot execute from a fresh checkout.

### Blockers / unknowns

- Recent base/anchored audit, hard-link, retention, audit-chain, remediation, watchdog, Loki, investigator, MCP, Gemini, metrics-bridge, identity/auth/readiness/activation/onboarding/Cloud Run hardening suites still require a current executable checkout for consolidated regression execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Audit the remaining local checkpoint/state filesystem writers for the same symlink/hard-link/path-substitution class of bugs, starting with `runtime/incident_checkpoint.py`; migrate only security-sensitive local state paths that still use ordinary pathname opens, add focused regressions, and run the consolidated audit/checkpoint/retention suites as soon as executable checkout is restored.**
