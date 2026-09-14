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
- Both unsigned and HMAC-signed local JSON checkpoint stores use the dedicated descriptor-bound checkpoint primitive; symlinks, hard-link aliases, post-open path substitution, unsafe truncation, and post-replace pathname chmod races are rejected or avoided.
- A genuinely absent local checkpoint preserves normal empty-store semantics (`None`) without reintroducing a separate `exists()`/open race.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — signed local checkpoint filesystem hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/checkpoint_file_security.py`, `runtime/incident_checkpoint.py`, `runtime/bootstrap.py`, `runtime/signed_json_checkpoint.py`, `runtime/tests/test_checkpoint_file_security.py`, and `runtime/tests/test_json_checkpoint_store_file_security.py`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The previously hardened `JsonCheckpointStore` was using the shared descriptor-bound checkpoint primitive, but the authenticated `SignedJsonCheckpointStore` still used the old `exists()`/`read_bytes()` load path and its own `mkstemp`/`os.replace`/post-replacement pathname `chmod` save path. This left the production-oriented local signed backend with weaker filesystem integrity than the unsigned backend: check/open races, hard-link acceptance, and a pathname permission-mutation race remained possible even though the document itself was HMAC-authenticated.

This was higher priority than expanding parent-directory policy because it was an active duplicated implementation on an explicitly selectable runtime backend (`--checkpoint-backend signed-json`).

### Exact changes made

1. Migrated `SignedJsonCheckpointStore.load()` to `read_private_bytes(path, max_bytes=_MAX_BYTES)` and preserved genuine `FileNotFoundError` as empty-store `None` semantics.
2. Migrated `SignedJsonCheckpointStore.save()` to `atomic_write_private_bytes(path, _encode(..., signing_key=...))`.
3. Removed duplicated `os` and `tempfile` filesystem code and the post-replacement pathname `chmod`.
4. Preserved HMAC-authenticated `_decode(..., require_signature=True)` semantics; filesystem hardening does not weaken document authenticity checks.
5. Added `runtime/tests/test_signed_json_checkpoint_file_security.py` covering:
   - missing signed checkpoint -> `None` without an `exists()` precheck;
   - signed round trip with single-link regular-file and owner-only mode invariants;
   - symlink load rejection without reading/mutating the target;
   - hard-link load rejection;
   - safe replacement of a symlink directory entry without mutating its target;
   - wrong signing-key rejection after secure read;
   - propagation of secure-reader path-identity failure;
   - delegation of signed writes to the atomic private writer with bounded encoded bytes.

Commits:
- `458cc7f643ae873d3be29ed90331de059771cf34` — Harden signed local checkpoint filesystem access
- `31923d5da1805152966071724b86517aeaf615b1` — Add signed checkpoint filesystem security regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- The committed production module was independently syntax-compiled with `python -m py_compile`: PASS.
- Fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` was attempted again so the signed and unsigned focused checkpoint suites could run together; checkout failed before execution with `Could not resolve host: github.com`.
- Therefore `runtime.tests.test_signed_json_checkpoint_file_security` and the current committed repository suite are not claimed green in this run.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Local signed and unsigned checkpoint backends must share one filesystem trust boundary; signing protects checkpoint contents, not pathname/inode integrity.
2. Missing local signed state remains a normal state-machine condition, while unsafe existing paths fail closed.
3. HMAC verification remains mandatory for the signed backend after secure descriptor-bound reading.
4. Parent-directory identity/ownership hardening remains worth reviewing, but duplicated insecure checkpoint I/O was a more immediate defect and is now removed.

### Blockers / unknowns

- Recent audit/checkpoint/retention and broader hardening regressions still require a current executable checkout for consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.
- The shared checkpoint primitive secures the final file entry itself but still creates/uses the parent directory by pathname; parent-directory substitution/ownership assumptions have not yet been formally hardened.

## Single best next step

**Run the focused signed+unsigned checkpoint suites immediately when executable checkout is restored; in parallel, review and, if portable, bind checkpoint atomic writes to a validated parent-directory descriptor so parent path substitution cannot redirect temp creation or final replacement.**
