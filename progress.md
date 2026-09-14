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
- A genuinely absent local checkpoint preserves normal empty-store semantics (`None`) without reintroducing a separate `exists()`/open race.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — checkpoint parent-bound reads

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/checkpoint_file_security.py`, `runtime/tests/test_checkpoint_file_security.py`, and the local checkpoint-store integration in `runtime/incident_checkpoint.py`. Confirmed that both unsigned `JsonCheckpointStore` and signed local checkpoint storage consume the shared bounded-read primitive, so strengthening `read_private_bytes()` protects both local backends without changing checkpoint serialization or incident lifecycle behavior. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

Atomic checkpoint writes were already parent-fd-bound on POSIX, but bounded reads still opened the full configured checkpoint pathname first and only then validated the resulting file descriptor. A parent directory substituted before that full-path open could therefore redirect which file was initially opened, even though later file-identity checks protected against final-component substitution.

Because checkpoint state controls replay safety and incident lifecycle restoration, the parent directory must be part of the read trust boundary as well as the write trust boundary.

### Exact changes made

1. Added `_supports_directory_relative_open()` capability detection for the POSIX production path using dir-fd-capable `os.open`, dir-fd-capable `os.stat`, and `follow_symlinks=False` support.
2. Added `_assert_private_regular_file_at_parent()` to validate a checkpoint descriptor against the exact basename visible inside one already-bound parent descriptor. It enforces regular-file shape, single-link ownership, exact `(st_dev, st_ino)` identity, non-symlink directory entry, and parent-path identity.
3. Added `_read_private_bytes_via_parent_fd()`:
   - validates and opens the parent directory once;
   - opens only `state_path.name` relative to that descriptor with `O_NOFOLLOW` where available;
   - preserves genuine `FileNotFoundError` semantics;
   - validates file and parent identity before reading;
   - performs the existing bounded descriptor read;
   - revalidates file and parent identity after reading before returning bytes.
4. Routed `read_private_bytes()` through the directory-relative implementation on supported POSIX systems while retaining the existing portable descriptor/path fallback elsewhere.
5. Added regression coverage proving:
   - a symlinked checkpoint parent is rejected without trusting the target directory;
   - swapping the parent after its descriptor is opened but immediately before the child basename open cannot redirect StageGuard into attacker-controlled state; the operation fails closed when the configured parent path no longer names the bound directory.

Commits:
- `7ed97a25050ab1877205137b60b3cceb8837aa5b` — Bind checkpoint reads to validated parent directory
- `2e9b0340c7feff37314f621896aa523067b9c9b7` — Add checkpoint parent-bound read regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- Re-read the committed `runtime/checkpoint_file_security.py` from `main` after the implementation commit to verify the intended production path was present.
- The runner reports the required POSIX capabilities (`os.open` and `os.stat` dir-fd support plus `os.stat(..., follow_symlinks=False)`) as available.
- Fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` was attempted for executable validation and still failed before checkout with `Could not resolve host: github.com`.
- Therefore the newly committed `runtime.tests.test_checkpoint_file_security` regressions are not claimed green in this run.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. A checkpoint read must bind both the containing directory and file entry; validating only the final file inode after a full-path open is insufficient against pre-open parent substitution.
2. If the configured parent path changes while a read is in progress, StageGuard fails closed even if the already-bound directory descriptor still points to a readable original file. Returning data would falsely imply that the configured checkpoint location remained authoritative.
3. Genuine absence remains distinguishable from an unsafe existing path so normal empty-store startup behavior is preserved.
4. Portable platforms retain the older descriptor/path validation path rather than pretending to provide the same race-free parent binding as POSIX dir-fd operations.

### Blockers / unknowns

- Recent audit/checkpoint/retention and broader hardening regressions still require a current executable checkout for consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.
- The generic `open_private_regular_file()` API is still full-path-based. Production checkpoint reads no longer depend on that path on POSIX, but direct callers and the portable atomic-write verification fallback still use it.

## Single best next step

**Migrate `open_private_regular_file()` itself onto the validated parent-directory descriptor model on supported POSIX systems, preserving `FileNotFoundError` and safe `O_CREAT` behavior, then add direct-open parent-swap regressions so every checkpoint file opener shares the same parent-binding guarantee.**
