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
- Local checkpoint parents must not be group- or world-writable, including sticky world-writable directories. Directory ownership equality is deliberately not required so container/volume ownership models can remain compatible when namespace permissions are otherwise private.
- A genuinely absent local checkpoint preserves normal empty-store semantics (`None`) without reintroducing a separate `exists()`/open race.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — checkpoint parent permission policy

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/checkpoint_file_security.py`, `runtime/tests/test_checkpoint_file_security.py`, `runtime/bootstrap.py`, and the runtime container definition. Confirmed that the checkpoint parent directory was identity-bound but its namespace permissions were not constrained. The default local checkpoint path is `.stageguard/incident-checkpoint.json`; production can also use GCS. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

Descriptor binding prevents parent-path substitution after open, but a group/world-writable parent still gives other principals unnecessary namespace mutation capability around local checkpoint state. Sticky-bit directories reduce unlink/rename attacks but do not provide the private namespace expected for durable incident state. Requiring the directory to be owned by the effective UID would be unnecessarily rigid for container and mounted-volume deployments, where ownership can legitimately differ while permissions/ACLs provide the intended isolation.

### Exact changes made

1. Hardened `_assert_directory_identity()` so local checkpoint parents fail closed when either `S_IWGRP` or `S_IWOTH` is set.
2. Enforced the permission check on both the opened directory descriptor and the currently visible parent pathname, alongside existing directory identity and symlink checks.
3. Deliberately did not require `st_uid == geteuid()`. This preserves compatibility with non-process-owned container/volume directories while still rejecting namespace permissions that are explicitly group/world writable.
4. Sticky world-writable directories such as mode `01777` are intentionally rejected for local checkpoint storage; deployments should use a private subdirectory instead.
5. Added `runtime/tests/test_checkpoint_parent_directory_policy.py` with regressions for group-writable, world-writable, sticky world-writable, non-mutation on rejection, and a normal private-directory checkpoint round trip.

Commits:
- `5ea9b2d258e32b153ee6889379b1ca8cb483dd96` — Reject unsafe writable checkpoint parent directories
- `0f8c98e76f16ebedbb1d8c1dcef50368c262abf4` — Add checkpoint parent permission policy regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- Fresh checkout plus focused test execution was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` followed by the parent-policy/checkpoint-security unittest modules.
- The run still failed before checkout with `Could not resolve host: github.com`; therefore the newly committed regressions are not claimed green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Local incident checkpoint state requires a private namespace, not merely a securely opened final file.
2. Group/world write bits are a clear, portable fail-closed signal and are rejected.
3. Sticky-bit public directories are not accepted as the checkpoint parent; operators can create a private child directory or use the GCS checkpoint backend.
4. Directory owner equality is not part of the invariant because container/volume ownership and ACL models can legitimately differ from the process UID.

### Blockers / unknowns

- Recent audit/checkpoint/retention and broader hardening regressions still require a current executable checkout for consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Move out of filesystem hardening and review the production operator path end-to-end: inspect incident investigation/evidence/diagnosis through approval, remediation, recovery verification, and UI state for any remaining user-visible dead ends or missing integration tests; implement the highest-impact functional gap found without depending on external credentials.**
