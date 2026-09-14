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
- A genuinely absent local checkpoint preserves normal empty-store semantics (`None`) without reintroducing a separate `exists()`/open race.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — checkpoint parent-directory binding

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/checkpoint_file_security.py` and `runtime/tests/test_checkpoint_file_security.py` first, with the previous run's signed/unsigned checkpoint integration state as the active baseline. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The checkpoint file entry itself was already protected by descriptor/path identity checks, single-link regular-file enforcement, symlink rejection, bounded reads, owner-only mode, and atomic replacement. However, `atomic_write_private_bytes()` still created its temporary file and performed final `os.replace()` by repeatedly resolving the parent pathname. A parent directory swapped between those operations could redirect a write even though the final checkpoint file primitive itself was secure.

This matters on the production Linux/Cloud Run path because checkpoint durability is part of the incident replay-safety boundary.

### Exact changes made

1. Added validated parent-directory descriptors with regular-directory and `(st_dev, st_ino)` identity checks plus final-component symlink rejection.
2. Added a POSIX directory-relative atomic-write path:
   - create the random private temporary file via `os.open(..., dir_fd=parent_fd, O_CREAT|O_EXCL)`;
   - write and `fsync()` through the file descriptor;
   - revalidate parent identity before replacement;
   - replace using `os.replace(..., src_dir_fd=parent_fd, dst_dir_fd=parent_fd)` so a pathname swap cannot redirect the operation;
   - validate final file shape/mode and `fsync()` the parent directory for rename durability;
   - revalidate the parent path again before returning.
3. Retained a portability fallback for platforms without directory-relative replacement, but added parent identity checks around every pathname-sensitive phase.
4. Corrected feature detection after confirming CPython exposes `os.replace(..., src_dir_fd=..., dst_dir_fd=...)` on POSIX while not listing `os.replace` separately in `os.supports_dir_fd`; support is now based on POSIX plus dir-fd-capable `os.open`/`os.rename`.
5. Added regressions for:
   - symlinked parent directories without target-directory mutation;
   - parent substitution after the temp file is written but before replacement, including temp cleanup in the displaced original directory;
   - a race immediately around replacement proving the dir-fd operation writes only to the originally opened parent, never the substituted pathname.
6. Fixed the replacement-race harness to use the captured real `os.replace` directly so patching the module's `os.replace` cannot recurse through `Path.replace()`.

Commits:
- `69a8be32a3e6e181f3ea186d122a3bca44b9a462` — Bind checkpoint atomic writes to validated parent directory
- `ad1de0bb51a22de0bc988d8e513af6ef4cb8f62a` — Detect directory-relative replace support portably
- `2cccd5b38f4039dea7de3579a987eb8bfb64307c` — Add checkpoint parent-directory substitution regressions
- `b3394f6e4a1f111486dde5eabe20ca7b29ecfefb` — Revalidate checkpoint parent after durable replace
- `9e928518855335def8a70cda9b1552086b1989c5` — Fix parent-directory race regression harness

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- The runner was checked for the actual runtime capability: `os.open` and `os.rename` are dir-fd capable on POSIX, and `os.replace` exposes `src_dir_fd`/`dst_dir_fd` even though it is not separately listed in `os.supports_dir_fd`.
- A minimal local syscall smoke using one directory descriptor successfully created a temp file and replaced it through `os.replace(..., src_dir_fd=..., dst_dir_fd=...)`: PASS.
- Fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` was attempted again for the committed regression suite and still failed before checkout with `Could not resolve host: github.com`.
- Therefore the committed `runtime.tests.test_checkpoint_file_security` suite is not claimed green in this run.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Parent-directory identity is part of the checkpoint trust boundary, not merely the final file inode.
2. Linux/Cloud Run should use directory-relative syscalls so the operation stays anchored even if the pathname is substituted after validation.
3. A detected parent substitution fails closed even when the replacement itself safely landed in the originally opened directory; returning success would give callers a false claim that the checkpoint is reachable at the configured path.
4. Portability fallbacks remain supported but cannot provide the same race-free guarantee as dir-fd operations; they therefore perform repeated identity checks instead of silently claiming equivalent protection.

### Blockers / unknowns

- Recent audit/checkpoint/retention and broader hardening regressions still require a current executable checkout for consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.
- Checkpoint writes are now parent-fd-bound on POSIX, but checkpoint reads/opening still resolve the full configured pathname before validating the file descriptor. A parent-path substitution that occurs before `open_private_regular_file()` resolves the path therefore remains worth reviewing, especially for the unsigned local backend.

## Single best next step

**Extend the validated parent-directory descriptor model to checkpoint reads/opening on POSIX: open the checkpoint basename relative to the bound parent fd, validate both parent and file identity before/after bounded reads, and add regressions proving a substituted parent path cannot redirect unsigned checkpoint reads.**
