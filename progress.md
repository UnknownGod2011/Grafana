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
- Local JSON checkpoint reads/writes now use a dedicated descriptor-bound primitive: symlinks, hard-link aliases, post-open path substitution, unsafe truncation, and post-replace pathname chmod races are rejected or avoided.
- A genuinely absent local checkpoint preserves normal empty-store semantics (`None`) without reintroducing a separate `exists()`/open race.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — JsonCheckpointStore secure primitive integration

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/incident_checkpoint.py`, `runtime/checkpoint_file_security.py`, existing checkpoint tests, and the `IncidentReport` model needed for store-level fixtures. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The dedicated checkpoint filesystem primitive existed, but `JsonCheckpointStore` was still bypassing it. `load()` performed `exists()`/`is_symlink()` checks followed by a separate pathname reopen, leaving a check/open race and accepting hard-link aliases. `save()` still used its own temporary-file implementation and performed `os.chmod(self.path, 0o600)` after replacement, leaving a pathname substitution race around the permission mutation.

During integration, one compatibility issue was also found: the secure opener wrapped a genuinely missing checkpoint path as `RuntimeError`, while `JsonCheckpointStore` historically treats a missing file as an empty store. That semantic needed to be preserved without restoring an `exists()` precheck.

### Exact changes made

1. Wired `JsonCheckpointStore.load()` to `read_private_bytes(path, max_bytes=_MAX_BYTES)` and decode only the bytes returned from the already-validated descriptor.
2. Wired `JsonCheckpointStore.save()` to `atomic_write_private_bytes(path, _encode(checkpoint))`, removing the duplicated temporary-file implementation and the post-replace pathname `chmod`.
3. Removed now-unused `os`/`tempfile` imports from `runtime/incident_checkpoint.py`.
4. Updated `open_private_regular_file()` so only a genuine `FileNotFoundError` is preserved for empty-store semantics; unsafe existing paths and other open failures still fail closed.
5. Added `runtime/tests/test_json_checkpoint_store_file_security.py` covering:
   - missing checkpoint -> `None` without a pathname precheck;
   - valid save/load round trip with owner-only, single-link regular-file state;
   - symlink load rejection without reading/mutating the target;
   - hard-link load rejection;
   - safe replacement of a symlink directory entry without mutating its target;
   - propagation of a post-open identity failure from the secure reader;
   - delegation of writes to the atomic private writer with bounded encoded bytes.

Commits:
- `2d773ee532fe6159b6c37cf02de9e00f9c30fc63` — Wire local checkpoint store to secure filesystem primitive
- `ce85004bae897be7454249fe56db6a00a8a6e63f` — Preserve missing checkpoint semantics in secure opener
- `04ccb27df8f87394ae175d2c1f6c48348b7ff8fe` — Add JsonCheckpointStore filesystem security regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- Inspected the integration commit diff after write: the production change is limited to the secure helper import plus `JsonCheckpointStore.load()`/`save()` replacement; Google Cloud Storage checkpoint logic and observable checkpoint telemetry were not changed.
- Fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` was attempted again and failed before checkout with `Could not resolve host: github.com`.
- Because executable checkout is unavailable, the newly committed store-level unittest file is not claimed green in this run.
- No GitHub Actions workflow was triggered merely to bypass the transient DNS failure.

### Decisions

1. Missing local state is a normal state-machine condition and remains distinguishable from unsafe filesystem state.
2. Existing symlink or hard-link checkpoint paths are never treated as equivalent to “missing”; they fail closed.
3. `JsonCheckpointStore` should remain a serialization/lifecycle adapter and delegate filesystem trust to one narrow primitive rather than maintaining a second implementation.
4. Atomic replacement may safely replace an existing symlink directory entry because the write originates from a validated private temporary inode and does not dereference the symlink target.

### Blockers / unknowns

- Recent audit/checkpoint/retention and broader hardening regressions still require a current executable checkout for consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.
- The checkpoint primitive currently secures the final file entry itself; the next filesystem review should explicitly consider whether parent-directory identity/ownership constraints are required for the local threat model before expanding the primitive further.

## Single best next step

**Run the focused checkpoint suites as soon as executable checkout is restored; meanwhile inspect `runtime/checkpoint_file_security.py` and local-state callers for parent-directory substitution/permission assumptions, and harden only if the threat model and existing deployment paths justify it.**
