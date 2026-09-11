# Evidence-unavailable incident lifecycle

StageGuard treats an observability-plane outage as a safety state, not as a diagnosis.

## Contract

When a required Grafana MCP/Prometheus/Loki evidence read fails with the adapter-neutral `EvidenceUnavailable` contract:

1. The investigator returns `status="abstain"` with `confidence=0.0` and no hypothesis.
2. `unavailable_evidence` identifies only the bounded semantic slot (for example `causal` or `causal_log`).
3. `missing_evidence` remains reserved for successful evidence queries that returned no authoritative sample.
4. Raw adapter/provider exception text is never copied into the incident report, lifecycle API, or audit timeline.
5. Evidence collection stops at the first required unavailable slot; partial evidence cannot become a diagnosis.
6. `IncidentService.approve()` rejects every report whose status is not `diagnosed` before creating an approval record.
7. No remediation provider call is possible without a valid diagnosed report and exact revision-bound approval.

## Operator/API semantics

The authenticated incident API already serializes `IncidentReport.to_dict()`, so clients receive both `missing_evidence` and `unavailable_evidence`. Consumers should render these differently:

- `missing_evidence`: query succeeded, but authoritative telemetry was absent.
- `unavailable_evidence`: StageGuard could not safely obtain required evidence from the observability plane.

Neither state should present an approval or execution affordance.

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

The next UI hardening step is to render a dedicated evidence-plane-unavailable safety card from the already-present `report.unavailable_evidence` field, while keeping all remediation controls disabled.
