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
- Local cooperative audit-lock sidecars must be owner-only regular files, may not be symbolic links, and the opened descriptor must match the exact file identity still visible at the sidecar path.
- Secure local audit data descriptors must name a single-link regular file that still matches the visible pathname; symbolic links, hard-link aliases, and path substitution fail closed.
- Anchored local JSONL audit reads/appends and local retention planning/execution use the shared secure descriptor primitive.
- Retention revalidates descriptor/path identity immediately before destructive pathname replacement and builds its recovery backup from the already-open authenticated source descriptor.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing tests.

## Run log — 2026-09-14 — Audit hard-link alias hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/incident_service.py`, `runtime/audit_file_lock.py`, `runtime/anchored_incident_service.py`, the runtime tree, and current audit security tests. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The shared secure audit opener rejected symbolic links, non-regular files, and descriptor/path identity changes, but it still accepted an existing regular file with more than one hard link. A malicious or accidental hard-link alias can expose the same inode through another pathname, so StageGuard could append audit bytes or apply `0600` permissions to a file reachable outside the intended audit path while `(st_dev, st_ino)` identity validation still succeeds. Retention would inherit the same aliasing risk because it deliberately operates on the authenticated inode.

The planned legacy `JsonlAuditLog` migration remains valid, but closing this shared primitive gap first protects every already-migrated anchored/retention caller and prevents propagating the weakness into the legacy migration.

### Exact changes made

1. Hardened `assert_open_regular_file_identity()` in `runtime/audit_file_lock.py` to require `st_nlink == 1` on the opened descriptor.
2. Added the same single-link requirement to the visible path recheck, so a second hard link created after open invalidates a long-lived descriptor before later mutation.
3. Kept symlink, regular-file, exact `(st_dev, st_ino)` identity, owner-only mode, `O_NOFOLLOW`, and no-`O_TRUNC` protections intact.
4. Documented why hard-link aliases are incompatible with StageGuard's local audit ownership boundary.
5. Added `runtime/tests/test_audit_file_hardlink_security.py` with regressions for:
   - rejecting a hard-linked audit pathname without modifying the peer pathname's bytes;
   - rejecting an already-open descriptor after a second hard link appears;
   - preserving normal single-link create/write behavior.
6. Tests skip cleanly only where the host filesystem cannot create hard links.

Commits:
- `4a0d930946e615759181e0e93fd7a74a4c45ea47` — Reject hard-linked local audit files
- `3ab67c2cd9d37229e01c5011651250049625e5f1` — Add audit hard-link security regressions

### Checks / results

- Authenticated GitHub connector inspection and writes succeeded on `UnknownGod2011/Grafana` `main`.
- A fresh executable checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/grafana.git`; the runner again failed before checkout with `Could not resolve host: github.com`.
- Intended focused command: `PYTHONPATH=runtime python -m unittest runtime.tests.test_audit_file_hardlink_security runtime.tests.test_audit_data_file_security runtime.tests.test_retention_path_security -v`.
- Because the runner cannot obtain a current checkout, the new regression suite is not claimed green.
- No GitHub Actions workflow was triggered merely to bypass the transient DNS failure.

### Decisions

1. A StageGuard-owned local audit file must have exactly one directory entry. Inode identity alone is insufficient when another hard-link pathname can mutate the same bytes.
2. The single-link invariant belongs in the shared secure descriptor primitive so anchored audit and retention inherit it automatically and the upcoming legacy audit migration cannot omit it.
3. Rechecking link count on long-lived descriptors matters because a second hard link can appear after the initial secure open.
4. This is intentionally stricter than a generic file opener: local audit integrity takes precedence over supporting hard-link-based snapshot schemes.

### Blockers / unknowns

- Base `JsonlAuditLog` in `runtime/incident_service.py` still uses ordinary pathname opens and remains the main local-demo gap.
- Recent hard-link, retention, audit-chain, remediation, watchdog, Loki, investigator, MCP, Gemini, metrics-bridge, identity/auth/readiness/activation/onboarding/Cloud Run hardening suites still require a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Migrate the legacy/base `JsonlAuditLog` create/append/read/candidate paths in `runtime/incident_service.py` onto `audit_file_lock()` + `open_regular_audit_file()`, add legacy-log symlink/hard-link/path-swap regressions, then run the consolidated audit + retention suites as soon as executable checkout is restored.**
