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
- Local cooperative audit-lock sidecars must be owner-only regular files and may not be symbolic links; platforms with `O_NOFOLLOW` use it at open time.

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
- Local audit locking refuses symlink/directory substitution for the sidecar used by anchored JSONL writes and retention coordination.
- Audit-chain canonicalization now enforces the same incident/event/actor envelope byte limits and ASCII-control rejection as durable Cloud Logging so an event cannot become authenticated chain state solely to be rejected at the durable sink boundary.

## Run log — 2026-09-13 — Audit-chain envelope contract alignment

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata, the runtime tree, `runtime/audit_integrity.py`, `runtime/cloud_audit.py`, `runtime/incident_service.py`, `runtime/audit_anchor.py`, and `runtime/tests/test_audit_integrity.py`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

`GoogleCloudLoggingAuditSink` already rejected non-string/empty envelope identifiers, ASCII control characters, and identifiers exceeding 256/128/512 UTF-8 bytes for `incident_id`/`event_type`/`actor`. `canonical_audit_event()` only required non-empty strings. Therefore the chain could authenticate lifecycle state that the durable Cloud Logging boundary would refuse, creating avoidable divergence between integrity authority and persistence authority.

### Exact changes made

1. Hardened `runtime/audit_integrity.py` with explicit `AuditEvent` type validation.
2. Added the durable envelope limits: incident ID 256 UTF-8 bytes, event type 128 bytes, actor 512 bytes.
3. Added ASCII control rejection for `0x00-0x1f` and `0x7f` before canonical hashing.
4. Kept the existing strict positive sequence, non-negative timestamp, dictionary payload, deterministic JSON, and `allow_nan=False` behavior.
5. Added regressions covering newline/NUL/ESC/DEL controls, non-string envelope values, multibyte UTF-8 over-limit values, exact accepted UTF-8 boundaries, and proof that rejected events do not advance the chain from genesis.

Commits:
- `de864657cd1e05c4089d4d7c1d60d150f22a6c15` — Align audit-chain envelope validation with durable audit contract
- `7dd7f45dd7a3e66a1be7149dd35857bd8031ea17` — Add audit-chain envelope contract regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Attempted a fresh checkout and focused execution with `PYTHONPATH=runtime python -m unittest runtime.tests.test_audit_integrity runtime.tests.test_cloud_audit -v`.
- The checkout failed before test execution with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.
- The new regressions are therefore not claimed green against the repository checkout/dependency set.

### Decisions

1. Hash-chain authority and durable audit persistence should agree on envelope identity validity; accepting a wider envelope at the integrity boundary creates unnecessary split-brain failure modes.
2. UTF-8 byte limits intentionally match Cloud Logging rather than Python character counts so multibyte identities behave identically across both boundaries.
3. Payload-policy parity was not broadened in this change: the chain authenticates the full lifecycle event, while the Cloud sink intentionally applies additional secret/key/size restrictions before export.
4. Existing hashes for already-valid production events are unchanged because canonical JSON serialization was not altered.

### Blockers / unknowns

- `runtime.tests.test_audit_integrity` and `runtime.tests.test_cloud_audit` still need a current executable repository checkout.
- Recent audit-lock, remediation, watchdog, Loki, investigator, MCP, Gemini, metrics-bridge, identity/auth/readiness/activation/onboarding/Cloud Run hardening suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, first run `PYTHONPATH=runtime python -m unittest runtime.tests.test_audit_integrity runtime.tests.test_cloud_audit -v` and fix any failure immediately. If clean, run the audit-lock/anchored-transition regressions, then the accumulated watchdog/remediation/Loki/investigator/MCP/Gemini/auth/readiness/bridge/activation suites before the pinned Grafana MCP 1.4.1 smoke and private Cloud Run metrics acceptance.**
