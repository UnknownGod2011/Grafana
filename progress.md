# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The working vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, pinned local acceptance images, strict Prometheus/MCP evidence parsing, and structured evidence-unavailable abstention.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, nonnumeric, or non-finite evidence must never be interpreted as healthy evidence.
- Expected evidence-plane transport/protocol failures become sanitized abstention, not diagnosis.
- Programming/configuration defects remain visible exceptions.
- Partial, missing, or unavailable evidence must never reach infrastructure mutation.

## Run log — 2026-09-11 — evidence-unavailable lifecycle contract

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the current default branch and the relevant lifecycle surfaces, including:
- `runtime/investigator.py`
- `runtime/incident_service.py`
- `runtime/api.py`
- `runtime/operator_console.py`
- `runtime/tests/test_incident_service.py`

The previous best next step was to carry `unavailable_evidence` through service/API/audit/UI and prove approval is rejected before an approval record is created.

### Exact changes made

#### Added end-to-end lifecycle regression coverage

Created `runtime/tests/test_evidence_unavailable_lifecycle.py`.

The regression creates a metric adapter that returns the symptom sample and then raises `EvidenceUnavailable` on the required causal read. It verifies:
- the service returns `status="abstain"`;
- `unavailable_evidence == ("causal",)` while `missing_evidence` remains empty;
- collection stops immediately at the failed required slot;
- the authenticated lifecycle serialization exposes only the semantic unavailable slot;
- provider exception content, endpoint-like text, and token-like text never enter the lifecycle JSON;
- the audit contains one `investigation_completed` event with bounded `status="abstain"` data;
- an approval attempt is rejected by `IncidentService.approve()` because the incident is not diagnosed;
- that rejection leaves `approval is None`, creates no `remediation_approved` audit event, and performs zero remediation calls;
- the public timeline remains sanitized and does not mislabel evidence unavailability as ordinary `missing_evidence`.

Commit:
- `cfd656e908466016d18cf54f050cdea0a7c8a3a8` — test evidence-unavailable lifecycle safety

#### Documented the lifecycle contract

Created `docs/evidence-unavailable-lifecycle.md` describing:
- the distinction between `missing_evidence` and `unavailable_evidence`;
- sanitization requirements;
- first-failure collection stopping;
- API/operator semantics;
- audit semantics;
- approval rejection before approval persistence;
- the requirement that remediation controls remain unavailable for both missing and unavailable evidence.

Commit:
- `33f78a3630005753d5844d5989a28c6360ca30bd` — document evidence-unavailable lifecycle contract

### Checks / results

Attempted a fresh executable checkout before editing:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container again failed with `Could not resolve host: github.com`, so the new unittest could not be executed locally and no green claim is made.

Repository inspection and writes succeeded through the connected GitHub integration. No GitHub Actions workflow was created, triggered, rerun, or modified. No Grafana Cloud, GCP/IAM/Cloud Run, Gemini, checkpoint, or remediation resource was changed.

Static contract checks performed while adding the regression:
- `IncidentReport.to_dict()` already serializes both `missing_evidence` and `unavailable_evidence`;
- `_lifecycle_view()` serializes the complete incident snapshot, so the unavailable slot is already present in authenticated API output;
- `IncidentService.approve()` checks `report.status == "diagnosed"` before constructing or recording an approval;
- timeline projection excludes raw provider/adapter error details.

### Decisions

1. Treat evidence unavailability as a first-class safety condition while keeping the bounded incident status `abstain`.
2. Keep availability and absence semantically distinct in every client: unavailability means the evidence plane could not safely answer; missing means the query succeeded but authoritative telemetry was absent.
3. Preserve the existing approval gate rather than creating a parallel approval-state mechanism: only `diagnosed` can ever be approved.
4. Regression-test the safety boundary before adding richer UI presentation so future UI work cannot accidentally weaken backend enforcement.
5. Do not trigger noisy CI merely because the local execution environment cannot currently resolve GitHub.

### Blockers / unknowns

- The new focused unittest still needs execution from a runnable checkout.
- The operator console still needs a dedicated evidence-plane-unavailable safety card; the backend/API field is already available.
- The complete credential-free Docker watchdog rehearsal still needs a current run against pinned Prometheus 3.13.3 and Grafana 13.2.1.
- The authenticated metrics bridge still needs disposable-project acceptance against a private Cloud Run StageGuard service using a least-privilege invoker identity.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**Update the operator console to render `report.unavailable_evidence` as an explicit evidence-plane-unavailable safety state, visibly distinct from `missing_evidence`, and keep briefing/approval/execution controls disabled for that state. Add static/UI regressions proving no provider exception text can be rendered. If a runnable checkout becomes available first, run `python -m unittest runtime.tests.test_evidence_unavailable_lifecycle` before further integration work.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
