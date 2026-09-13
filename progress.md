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
- Local audit locking rejects obvious symlink/directory substitution and now also verifies post-open descriptor/path identity to detect check/open replacement on platforms without `O_NOFOLLOW`.

## Run log — 2026-09-13 — Audit-lock post-open identity hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata, `runtime/audit_file_lock.py`, `runtime/tests/test_audit_file_lock.py`, local audit integration points, and the current retained validation/blocker state. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The lock sidecar already rejected a pre-existing symbolic link and used `O_NOFOLLOW` when available, but on platforms where `O_NOFOLLOW` is absent there remained a check/open substitution gap: a path could change between the pre-open `is_symlink()` check and `os.open()`. A regular target reached through that race would pass the existing descriptor regular-file check.

### Exact changes made

1. Added `_same_file_identity()` to compare the opened descriptor's `(st_dev, st_ino)` with the post-open `lstat()` identity of the visible sidecar path.
2. `_open_lock_sidecar()` now performs a post-open `lstat()`, rejects a symlink/non-regular visible path, and rejects descriptor/path identity mismatch before applying permissions or entering lock coordination.
3. Failure paths still close the descriptor before propagating the error.
4. Added regressions that simulate a post-open identity substitution and verify rejection, plus a positive test proving a normal sidecar descriptor matches the visible regular file.

Commits:
- `b1901bf7580ba7138641f9328a2cb936eb0d5b21` — Harden audit lock sidecar identity validation
- `be791fbf5106ebabd258c603e049990771ec94b4` — Add audit lock identity substitution regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- A fresh local clone was attempted before implementation and still failed with `Could not resolve host: github.com`.
- Because executable checkout remains unavailable, `runtime.tests.test_audit_file_lock` is not claimed green in this run.
- A minimal local Python syntax sanity check for the new identity-comparison expression passed.
- No GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.

### Decisions

1. Sidecar safety should bind to file identity, not only pathname type checks; otherwise the cooperative lock can be redirected during the open window on platforms without `O_NOFOLLOW`.
2. Device+inode equality is intentionally used after open because it validates the descriptor against the current directory entry without following a symlink.
3. This change remains scoped to the cooperative lock sidecar; hardening the audit JSONL data path itself against equivalent substitution is a separate follow-up and should be implemented with the same no-follow/regular-file identity discipline.

### Blockers / unknowns

- `runtime.tests.test_audit_file_lock` still needs a current executable repository checkout.
- The audit JSONL data file itself still uses ordinary path opens and should receive equivalent symlink/identity hardening.
- Recent audit-chain, remediation, watchdog, Loki, investigator, MCP, Gemini, metrics-bridge, identity/auth/readiness/activation/onboarding/Cloud Run hardening suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Harden the local audit JSONL data-file open/read/append boundary itself against symlink and path-identity substitution, then run `PYTHONPATH=runtime python -m pytest runtime/tests/test_audit_file_lock.py -q` plus the relevant anchored-audit tests as soon as executable checkout works.**
