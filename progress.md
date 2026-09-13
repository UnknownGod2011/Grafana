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
- Local checkpoint filesystem hardening is being moved to the same fail-closed descriptor identity model: symbolic links, hard-link aliases, post-open path substitution, and pathname chmod races must not be trusted.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — Local checkpoint filesystem security primitive

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata, `runtime/incident_checkpoint.py`, and `runtime/audit_file_lock.py`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

`JsonCheckpointStore.load()` still trusted ordinary pathname I/O (`Path.exists()`, `Path.is_symlink()`, then `Path.read_bytes()`). That leaves a check/open race and accepts hard-link aliases. `save()` writes through a safe temporary descriptor but performs a pathname `chmod()` after `os.replace()`, which creates a separate substitution race: a path changed after replacement could receive StageGuard's permission mutation.

### Exact changes made

1. Added `runtime/checkpoint_file_security.py`, a dedicated local checkpoint filesystem primitive with:
   - no-follow opens when supported;
   - single-link regular-file enforcement;
   - exact `(st_dev, st_ino)` descriptor/path identity checks;
   - rejection of `O_TRUNC` before validation;
   - bounded descriptor-based reads with a post-read identity recheck;
   - atomic owner-only writes through a same-directory temporary descriptor;
   - no pathname chmod after final replacement;
   - final descriptor/path verification after replacement.
2. Added `runtime/tests/test_checkpoint_file_security.py` covering symlink rejection without target mutation, hard-link rejection, post-open path replacement, bounded reads, owner-only/single-link atomic round trips, and replacement of a symlink directory entry without mutating its target.

Commits:
- `d3cb7b6084b8343556cbb62ca16c645ae18a2afb` — Add secure local checkpoint file primitive
- `7197965fc31c50aafbdf79a6eba34ece485ede72` — Add checkpoint file security regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- Fresh checkout was attempted again and failed before repository execution with `Could not resolve host: github.com`.
- Independently exercised the new primitive locally without repository/network dependencies: symlink rejection preserved the target, hard-link aliasing was rejected, and an atomic round trip produced a single-link regular file with mode `0600`. Result: `checkpoint security primitive smoke: PASS`.
- The committed unittest file itself is not claimed green in a fresh checkout because the runner still cannot obtain the repository through normal Git/DNS.
- No GitHub Actions workflow was triggered merely to bypass the transient DNS failure.

### Decisions

1. Checkpoint serialization/integrity and filesystem-path integrity remain separate concerns; the new primitive handles only the latter.
2. Local checkpoint reads should trust an already-open validated descriptor, not a pre-check followed by a pathname reopen.
3. Atomic checkpoint replacement should inherit permissions from the validated temporary inode and avoid any post-replace pathname chmod.
4. Existing audit helpers remain audit-specific; checkpoint state gets a narrowly named primitive rather than coupling unrelated local-state semantics to audit code.

### Blockers / unknowns

- `JsonCheckpointStore` still needs to be wired onto `read_private_bytes()` and `atomic_write_private_bytes()`; that integration is the next concrete change.
- Recent audit/checkpoint/retention and broader hardening regressions still require a current executable checkout for consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Wire `JsonCheckpointStore.load()` and `save()` in `runtime/incident_checkpoint.py` onto the new descriptor-bound checkpoint primitive, remove the post-replace pathname chmod race, add store-level symlink/hard-link/path-swap regressions, and run the focused checkpoint suite as soon as executable checkout is restored.**
