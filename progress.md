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
- Anchored local JSONL audit data reads/appends use no-follow regular-file descriptors with post-open pathname identity validation.
- Local JSONL retention planning and execution now use the same descriptor-bound audit-file primitive; execution revalidates descriptor/path identity immediately before the destructive pathname replace and builds the recovery backup from the already-open authenticated source descriptor.

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
- Anchored local JSONL creation/read/append and local retention scan/execution paths use the shared secure descriptor opener.

## Run log — 2026-09-13 — Retention path-substitution hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/audit_file_lock.py`, `runtime/incident_service.py`, `runtime/retention_planner.py`, `runtime/retention_executor.py`, and existing retention executor tests. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The anchored JSONL audit path had already been hardened, but local retention still reopened the audit pathname with ordinary `Path.open()`/`shutil.copyfile()` operations. A path could therefore be substituted between an earlier symlink/stat check and a later scan, backup copy, or final replace. The legacy base `JsonlAuditLog` also still uses ordinary pathname opens and remains a separate follow-up surface.

### Exact changes made

1. Added public `assert_open_regular_file_identity(fd, path)` in `runtime/audit_file_lock.py` so long-lived operations can revalidate that an opened descriptor still corresponds to the same visible regular file before pathname mutation.
2. Refactored `open_regular_audit_file()` to use that shared identity assertion while preserving no-follow, regular-file, owner-only, and no-`O_TRUNC` behavior.
3. Migrated `plan_jsonl_retention()` to the cooperative audit lock plus `open_regular_audit_file()` instead of ordinary `Path.open()` reads. Symlink/path substitution now becomes a fail-closed retention refusal rather than evidence.
4. Migrated retention file hashing to secure descriptor reads.
5. Migrated `execute_local_retention()` to hold the cooperative audit lock for execution, open the source through the secure descriptor primitive, and process the exact opened inode.
6. Removed pathname-based `shutil.copyfile()` backup creation. The backup is now created with `O_CREAT|O_EXCL` and populated by rewinding/copying the already-open authenticated source descriptor.
7. Added descriptor/path identity checks before backup creation and immediately before `os.replace()`. If the visible audit pathname changes while execution is in progress, compaction fails before replacing the substituted path.
8. Added `runtime/tests/test_retention_path_security.py` covering planner refusal for symlinked audit input, execution refusal after symlink substitution without target mutation, and an in-process post-open path swap immediately before replacement.

Commits:
- `2c48112f264565dacf806d5fddf340454ba71dd5` — Expose audit file descriptor identity validation
- `20e11722494bf6d05be69d2fa1110a0671e05de6` — Secure retention planner audit reads
- `90d41bc9a24accecf53a16ac4b7f8a1c3c9910ca` — Bind retention execution to secure audit descriptors
- `4563d310dea87e30d43132d21e5694239247a35b` — Add retention path substitution regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and all implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Fresh executable checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/grafana.git`; the runner still failed before checkout with `Could not resolve host: github.com`.
- Intended focused command remains: `PYTHONPATH=runtime python -m unittest runtime.tests.test_retention_path_security runtime.tests.test_retention_executor runtime.tests.test_retention_planner -v`.
- Because checkout remains unavailable, the new retention regressions and existing retention suites are not claimed green.
- No GitHub Actions workflow was triggered merely to bypass the transient DNS failure.

### Decisions

1. Retention must authenticate the file object it is operating on, not merely validate a pathname once.
2. The recovery backup must come from the exact source descriptor whose digest/candidate set was validated; reopening the pathname for backup would reintroduce substitution risk.
3. A second identity assertion immediately before `os.replace()` is required because a valid open descriptor does not prove the directory entry still points to that descriptor's inode.
4. Cooperative locking is retained for legitimate StageGuard writers, while descriptor/path identity checks independently fail closed against non-cooperating pathname replacement.

### Blockers / unknowns

- New retention path-security regressions require a current executable repository checkout.
- Base `JsonlAuditLog` in `incident_service.py` still uses ordinary pathname opens and should be migrated to the shared secure primitive to remove the remaining legacy/local-demo gap.
- Retention prepare still uses pathname `stat()` snapshots around separately secured inventory/hash passes; these detect ordinary drift but could be simplified into a single descriptor-bound prepare transaction in a future hardening pass.
- Recent audit-chain, remediation, watchdog, Loki, investigator, MCP, Gemini, metrics-bridge, identity/auth/readiness/activation/onboarding/Cloud Run hardening suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Migrate the legacy/base `JsonlAuditLog` create/append/read/candidate paths in `incident_service.py` onto `open_regular_audit_file()` (ideally under the same cooperative lock), add legacy-log symlink/path-swap regressions, then run the consolidated audit + retention suites as soon as executable checkout is restored.**
