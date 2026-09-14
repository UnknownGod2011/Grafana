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
- Production remediation HTTP requests never follow redirects and do not redirect bearer/idempotency authority.
- Authentication/identity inputs are bounded and attacker-controlled credentials are bounded before comparison.
- Metric activation v2 pins the exact ordered eight-query profile contract; Loki activation v2 pins policy-owned LogQL/limit and bounded preflight evidence.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; read-only/tool-surface restrictions are regression-locked.
- Core remediation watchdog clocks are finite native numbers; invalid/backward active clocks fail readiness closed.
- Local cooperative audit-lock sidecars must be owner-only, single-link regular files, may not be symbolic links, and the opened descriptor must match the exact file identity still visible at the sidecar path.
- Secure local audit data descriptors must name a single-link regular file that still matches the visible pathname; symbolic links, hard-link aliases, and path substitution fail closed.
- Base and anchored local JSONL audit create/read/append paths use the shared secure descriptor primitive under the cooperative audit lock.
- Retention planning/execution uses the shared secure descriptor primitive, revalidates descriptor/path identity immediately before destructive pathname replacement, and builds recovery backups from the already-open authenticated source descriptor.
- Both unsigned and HMAC-signed local JSON checkpoint stores use the dedicated descriptor-bound checkpoint primitive; symlinks, hard-link aliases, post-open file substitution, unsafe truncation, and post-replace pathname chmod races are rejected or avoided.
- On POSIX/Cloud Run, checkpoint atomic writes bind temporary creation and final replacement to one validated parent-directory descriptor; parent-path substitution cannot redirect the write into a substituted directory.
- On POSIX/Cloud Run, checkpoint bounded reads bind the basename open and subsequent file-identity checks to one validated parent-directory descriptor; parent-path substitution cannot redirect a read into a substituted directory.
- On POSIX/Cloud Run, the generic secure checkpoint opener also binds existing-file opens and `O_CREAT` creation to one validated parent-directory descriptor before returning a file descriptor.
- A genuinely absent local checkpoint preserves normal empty-store semantics (`None`) without reintroducing a separate `exists()`/open race.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — parent-bound generic checkpoint opens

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/checkpoint_file_security.py` and `runtime/tests/test_checkpoint_file_security.py`. Confirmed that bounded production reads and atomic writes were already parent-fd-bound on POSIX, while `open_private_regular_file()` still opened the complete configured pathname directly. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The generic secure checkpoint opener still represented a weaker filesystem boundary than the dedicated read/write paths. A caller using `open_private_regular_file()` directly could resolve a substituted parent directory before final-component validation. This was especially undesirable because the API explicitly supports both existing-file opens and safe `O_CREAT` creation.

### Exact changes made

1. Added `_open_private_regular_file_via_parent_fd()` for supported POSIX systems.
2. The helper opens and validates the configured parent directory once, then opens only `state_path.name` relative to that descriptor using `O_NOFOLLOW` where available.
3. The returned file must be a single-link regular file matching the exact directory entry in the bound parent, and the configured parent pathname must still name the same directory before and after the owner-only `fchmod` step.
4. `FileNotFoundError` remains distinguishable for genuinely absent files, and `O_TRUNC` remains prohibited.
5. `O_CREAT`/`O_EXCL` creation now occurs inside the already-bound parent directory instead of resolving the full pathname at creation time.
6. Portable platforms retain the existing full-path implementation with file-identity checks rather than claiming POSIX-equivalent parent-binding guarantees.
7. Added direct regressions covering a symlinked parent, a parent swap immediately before the basename open, and a normal parent-bound `O_CREAT|O_EXCL` round trip that produces a single-link `0600` regular file.

Commits:
- `0438b8c81e0275da9fec5fb5dccf453683e5adc8` — Bind generic checkpoint opens to parent directory
- `ba67f7da3e8b4359269ad0a71428b65aad436704` — Add parent-bound generic checkpoint open regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- Fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` was attempted after both implementation and regression commits and still failed before checkout with `Could not resolve host: github.com`.
- Therefore the newly committed `runtime.tests.test_checkpoint_file_security` regressions are not claimed green in this run.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Direct secure checkpoint opens must have the same parent-directory trust boundary as higher-level reads and writes on the Linux/Cloud Run production path.
2. Parent substitution after directory binding fails closed even when the already-open parent descriptor still points to a valid original directory; the configured checkpoint pathname must remain authoritative for the entire open operation.
3. Creation is anchored to the bound directory descriptor. This prevents an attacker-controlled replacement parent from receiving newly created checkpoint state.
4. The portable fallback keeps explicit weaker guarantees instead of emulating unsupported dir-fd behavior unsafely.

### Blockers / unknowns

- Recent audit/checkpoint/retention and broader hardening regressions still require a current executable checkout for consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.
- The checkpoint parent directory itself is identity-bound but not yet constrained by ownership/writeability policy; deployment assumptions currently rely on the process account and configured state directory.

## Single best next step

**Audit the checkpoint parent-directory ownership and writeability assumptions, then decide whether local checkpoint state should fail closed when the parent directory is group/world-writable or not owned by the effective StageGuard user; add focused regressions only if that policy is compatible with Cloud Run/container deployment.**
