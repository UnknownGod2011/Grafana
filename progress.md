# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The working vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, pinned local acceptance images, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, and an explicit fail-closed operator state for observability-plane outages.

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
- The browser must never turn evidence unavailability into an actionable diagnosis or expose provider failure detail.

## Run log — 2026-09-11 — operator evidence-plane safety state

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the current default branch and the relevant operator/lifecycle surfaces:
- `runtime/operator_console.py`
- `runtime/tests/test_operator_console.py`
- `docs/evidence-unavailable-lifecycle.md`
- recent commits on `main`

Confirmed the backend already serializes the bounded `unavailable_evidence` field and rejects approval for every non-`diagnosed` report. The remaining highest-value gap was the operator console, which did not yet render evidence-plane unavailability as a dedicated safety state and still allowed the Gemini briefing control to become enabled for a generic abstention.

### Exact changes made

#### Added explicit evidence-plane-unavailable operator state

Updated `runtime/operator_console.py`.

The same-origin cockpit now:
- renders a dedicated `Evidence plane unavailable` safety card with `aria-live="assertive"`;
- recognizes the bounded condition only when `report.status == "abstain"` and `unavailable_evidence` is non-empty;
- renders fixed safety copy instead of raw provider/adapter error text;
- displays the root cause as `Not established` and confidence as abstained/zero;
- marks the evidence source as unavailable without exposing provider details;
- disables Gemini briefing unless the current report is `diagnosed`;
- disables revision entry/approval unless the current report is `diagnosed`;
- requires a diagnosed report in addition to an approval before execution can be enabled;
- instructs the operator to restore the evidence plane and perform a fresh investigation;
- uses a fixed allowlist to convert semantic evidence slots such as `causal` and `causal_log` into human-readable labels, so arbitrary server strings are not copied into the DOM;
- keeps the existing checkpoint/audit fail-closed controls intact.

The first-viewport proof layer also renders evidence unavailability with fixed operator-facing safety copy and stops any recovery polling for that incident.

Commit:
- `9d4e2ba8f36a4e3e28b377df1c6e7d043cf61024` — render evidence-plane outage as fail-closed operator state

#### Added operator regression coverage

Updated `runtime/tests/test_operator_console.py` with a dedicated evidence-unavailable UI contract.

The regression checks:
- the safety card exists;
- the UI keys off the bounded abstain + `unavailable_evidence` contract;
- briefing and approval inputs require a diagnosed report;
- execution also requires a diagnosed report;
- semantic evidence slots pass through `safeEvidenceSlots` / `evidenceSlotLabels`;
- raw `unavailable_evidence.join(...)` rendering is absent;
- provider URLs and remediation operation IDs remain absent from the browser asset;
- fixed operator copy explicitly says provider error details are withheld.

The pre-existing checkpoint recovery assertion was updated to reflect the stronger execution guard while retaining the original fail-closed behavior.

Commit:
- `9bef39ad807e5520e6a5c5780d018bc937cafc10` — test evidence-unavailable operator safety state

#### Updated lifecycle documentation

Updated `docs/evidence-unavailable-lifecycle.md` to document the browser safety boundary, semantic-slot allowlisting, fixed operator copy, disabled controls, and the requirement for a fresh diagnosed revision before any approval/execution affordance can return.

Commit:
- `abfb4af70fd204fd939fded1bc50df1e7a2f869c` — document operator evidence-unavailable safety state

### Checks / results

Attempted a fresh executable checkout before editing:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container again failed with `Could not resolve host: github.com`, so no Python unittest or browser/runtime test could be executed locally and no green claim is made.

Repository reads/writes and post-write inspection succeeded through the connected GitHub integration. The committed operator asset was re-read after the change to verify the new safety card and fail-closed guards are present.

No GitHub Actions workflow was created, triggered, rerun, or modified. No Grafana Cloud, GCP/IAM/Cloud Run, Gemini, checkpoint, audit, or remediation resource was changed.

### Decisions

1. Treat evidence-plane unavailability as a first-class browser safety state, not merely a generic `abstain` badge.
2. Disable Gemini briefing for all non-diagnosed reports; an advisory summary must not make an evidence outage look more authoritative than the deterministic incident state.
3. Require `diagnosed` at every browser-side approval/execution affordance even though the backend already enforces the same invariant. UI defense-in-depth must never replace server enforcement.
4. Do not render raw `unavailable_evidence` values. Map only known semantic slots through an allowlist and fall back to generic fixed copy.
5. Keep provider/adapter failure detail out of the DOM entirely. Operators need the safety condition and bounded slot, not tokens, endpoints, exception bodies, or transport internals.
6. Do not trigger noisy CI merely because the local execution environment cannot currently resolve GitHub.

### Blockers / unknowns

- The updated `runtime.tests.test_operator_console` suite still needs execution from a runnable checkout.
- `runtime.tests.test_evidence_unavailable_lifecycle` also still needs a current executable run.
- The complete credential-free Docker watchdog rehearsal still needs a current run against pinned Prometheus 3.13.3 and Grafana 13.2.1.
- The authenticated metrics bridge still needs disposable-project acceptance against a private Cloud Run StageGuard service using a least-privilege invoker identity.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**Add an executable browser-level/operator integration test that feeds a real authenticated `/v1/incident` snapshot with `status="abstain"` and `unavailable_evidence`, then proves the evidence-plane safety card is visible while briefing, approval input, approval, and execution controls are disabled and no injected provider-error sentinel reaches rendered text. If a runnable checkout becomes available first, run `python -m unittest runtime.tests.test_operator_console runtime.tests.test_evidence_unavailable_lifecycle` and fix any regression before further feature work.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
