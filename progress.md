# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after accepted remediation, a fixed-cardinality recovery lifecycle contract shared by lifecycle JSON/readiness/Prometheus/Grafana, and a browser cockpit that consumes that server-derived recovery contract.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Investigation and recovery accept only finite non-boolean numeric metric evidence; malformed samples become unavailable and can never prove diagnosis/recovery.
- Loki corroboration validates adapter envelopes, exact evidence windows, record budgets/shapes, scope, and event identity before corroborating a diagnosis.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; remediation acceptance requires literal boolean `True`.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Once an accepted provider action has produced `recovery_unverified`, follow-up verification uses a recovery-only path with no remediation client and therefore cannot replay the provider side effect.
- Durable `recovery_unverified` state survives restart and remains eligible only for recovery-only verification; `recovered` is terminal.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Production remediation HTTP requests never follow redirects and do not redirect bearer/idempotency authority.
- Authentication/identity inputs are bounded and attacker-controlled credentials are bounded before comparison.
- Metric activation v2 pins the exact ordered eight-query profile contract; Loki activation v2 pins policy-owned LogQL/limit and bounded preflight evidence.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; read-only/tool-surface restrictions are regression-locked.
- Core remediation watchdog clocks are finite native numbers; invalid/backward active clocks fail readiness closed.
- Local audit/checkpoint state is symlink/hard-link/path-substitution hardened and owner-private; POSIX checkpoint access is parent-directory-descriptor bound.
- Local checkpoint parents must not be group- or world-writable, including sticky world-writable directories.
- Recovery observability is fixed-cardinality and provider-detail-free.
- Durable recovery outcome and execution phase must agree; mismatch fails readiness closed and has a critical Grafana alert.
- The browser cockpit trusts the authenticated server-produced recovery contract. Missing, malformed, self-inconsistent, or checkpoint-inconsistent recovery data fails closed and disables lifecycle mutations.
- The browser recovery control must use only `POST /v1/recovery/recheck`; the operator UI must never infer a need to invoke `/v1/execute` when recovery is already `recovery_unverified`.
- Fast local recovery-safety validation must execute the real embedded operator-console JavaScript; missing Node is an explicit validation failure rather than a silently skipped browser safety check.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API/Grafana/operator regressions remain blocked from repository execution because this automation runner cannot resolve `github.com`; authenticated connector reads/writes work, but commits are not treated as passing tests.

## Run log — 2026-09-14 — recovery safety documentation and API surface coherence

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata/root contents, the main `README.md`, `OPERATOR_CONSOLE.md`, and `scripts/run_recovery_safety_suite.py`. Confirmed the prior run's highest-priority deliverable existed as code but was not visible from the main README, and confirmed the README's authenticated HTTP surface list omitted the already-implemented `POST /v1/recovery/recheck` endpoint.

Attempted the intended fresh checkout and focused safety command first:

```bash
python scripts/run_recovery_safety_suite.py
```

The environment again failed during `git clone` with `Could not resolve host: github.com`, before any repository test could execute. Authenticated GitHub connector access remained available, so work continued through that channel without triggering GitHub Actions.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Updated `README.md` to document `POST /v1/recovery/recheck` in the authenticated operator HTTP surfaces.
2. Documented the endpoint's critical no-replay property directly in the main README: it performs recovery-only Grafana verification after an already accepted provider action and has no remediation client capable of redispatching the provider mutation.
3. Strengthened the README recovery safety-model row so accepted-but-unverified remediation is explicitly routed only to the recovery-only recheck path rather than another execution.
4. Added a `Fast recovery/no-replay safety validation` section with the canonical command:

   ```bash
   python scripts/run_recovery_safety_suite.py
   ```

5. Documented exactly what the focused runner covers: recovery observability, anchored recovery-only behavior, authenticated HTTP rechecks, restart durability, and the executable operator-console DOM/request harnesses.
6. Documented prerequisites and non-requirements: Python + Node.js are required; Grafana, Gemini, remediation/provider credentials, Docker, browser downloads, npm packages, and paid cloud resources are not.
7. Documented that missing Node is a hard validation failure so browser-level no-replay safety cannot silently skip.
8. Explicitly stated that the focused recovery safety command is a fast high-risk-boundary gate, not a replacement for the full regression suite or live Grafana MCP/Docker rehearsals.
9. Added `scripts/run_recovery_safety_suite.py` to the README repository structure so developers/operators can discover the safety entrypoint without reading `progress.md`.

Commit:
- `6cf62c3e70afe36afef1c5a667ad20821e5875e0` — Document recovery recheck and focused safety suite

### Checks / results

- Authenticated GitHub connector read/write operations succeeded against `UnknownGod2011/Grafana`.
- Re-fetched the updated README from `main` and confirmed the authenticated HTTP list now contains `POST /v1/recovery/recheck` with no-replay semantics.
- Re-fetched the local-development section and confirmed the focused runner command, Node requirement, dependency-light scope, and non-replacement warning are present.
- Inspected `OPERATOR_CONSOLE.md` and confirmed its existing recovery-recheck semantics agree with the new README wording: only fresh Grafana recovery telemetry is collected, the consumed approval is not reused, and no remediation client is present on the recheck path.
- Inspected `scripts/run_recovery_safety_suite.py` and confirmed the README's documented test scope/prerequisites match the committed runner implementation.
- Attempted a fresh shallow checkout plus `python scripts/run_recovery_safety_suite.py`; checkout failed before tests with `Could not resolve host: github.com`.
- Therefore this run does **not** claim the focused recovery suite green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Treat missing documentation of a safety-critical endpoint as a production usability defect, not cosmetic documentation debt: operators and integrators should discover the no-replay recovery path from the main README.
2. Keep the focused recovery suite dependency-light and developer-invoked rather than adding a noisy CI workflow while the project explicitly avoids unnecessary GitHub Actions usage.
3. Keep the README honest about validation scope: the recovery runner is a high-risk-boundary fast gate, while the historical full-suite failures and live MCP 1.4.1 smoke remain separate obligations.
4. Do not duplicate recovery implementation merely because the runtime checkout is unavailable; use authenticated repository inspection to eliminate documentation/API-surface drift while preserving the existing implementation contract.

### Blockers / unknowns

- This automation runner still cannot resolve `github.com`, so a current repository checkout and executable focused suite remain unavailable here.
- Recent audit/checkpoint/retention/recovery/Grafana regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as repository checkout is executable, run `python scripts/run_recovery_safety_suite.py` and fix every failure until the focused recovery/no-replay suite is green. If that passes, stop adding recovery-only assertions and move to the highest-impact unresolved production gap: triage the historical full-suite failures/errors into true defects versus obsolete tests, fixing the highest-severity real defect first while keeping GitHub Actions quiet.**
