# Evidence-unavailable incident lifecycle

StageGuard treats an observability-plane outage as a safety state, not as a diagnosis.

## Contract

When a required Grafana MCP/Prometheus/Loki evidence read fails with the adapter-neutral `EvidenceUnavailable` contract:

1. The investigator returns `status="abstain"` with `confidence=0.0` and no hypothesis.
2. `unavailable_evidence` identifies only the bounded semantic slot (for example `causal` or `causal_log`).
3. `missing_evidence` remains reserved for successful evidence queries that returned no authoritative sample.
4. Raw adapter/provider exception text is never copied into the incident report, lifecycle API, audit timeline, or operator DOM.
5. Evidence collection stops at the first required unavailable slot; partial evidence cannot become a diagnosis.
6. `IncidentService.approve()` rejects every report whose status is not `diagnosed` before creating an approval record.
7. No remediation provider call is possible without a valid diagnosed report and exact revision-bound approval.

## Operator/API semantics

The authenticated incident API serializes `IncidentReport.to_dict()`, so clients receive both `missing_evidence` and `unavailable_evidence`. Consumers must render these differently:

- `missing_evidence`: query succeeded, but authoritative telemetry was absent.
- `unavailable_evidence`: StageGuard could not safely obtain required evidence from the observability plane.

The same-origin operator cockpit renders `unavailable_evidence` as an explicit **Evidence plane unavailable** card and connection state. It deliberately uses fixed safety copy rather than provider exception text. Semantic slot names are passed through a fixed allowlist before they are turned into human-readable labels; unknown values are not copied into the DOM.

For an evidence-unavailable incident:

- the displayed root cause is `Not established`;
- confidence is presented as abstained/zero rather than as a weak diagnosis;
- Gemini briefing is disabled;
- revision entry for approval is disabled;
- approval remains disabled;
- execution remains disabled;
- the operator is instructed to restore observability and run a fresh investigation.

A fresh diagnosed revision is required before any approval or execution affordance can become available again. Existing partial evidence never becomes authorization material.

## Audit semantics

`investigation_completed` remains the lifecycle event for an unavailable evidence plane and records the bounded status (`abstain`), confidence, revision, and evidence mode. Provider errors, tokens, endpoints, query text, and exception bodies are excluded from the public timeline.

Approval rejection is intentionally not recorded as `remediation_approved`; a rejected approval attempt must leave the incident snapshot without an approval and must not call the remediation adapter.

## Regression coverage

`runtime/tests/test_evidence_unavailable_lifecycle.py` covers:

- sanitized service/API propagation of `unavailable_evidence`;
- strict separation from `missing_evidence`;
- first-failure collection stopping;
- audit sanitization;
- approval rejection before any approval audit record;
- zero remediation-provider calls after rejected approval.

`runtime/tests/test_operator_console.py` additionally covers the browser safety boundary:

- the dedicated evidence-plane-unavailable safety card exists;
- the UI detects only the bounded abstain + `unavailable_evidence` state;
- briefing and approval inputs are disabled unless the current report is diagnosed;
- execution requires a diagnosed report in addition to an approval;
- semantic evidence slots are converted through an allowlist rather than rendered raw;
- provider URLs, operation IDs, and raw unavailable slot joins are absent from the operator asset.
