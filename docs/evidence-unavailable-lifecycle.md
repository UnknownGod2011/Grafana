# Evidence-unavailable incident lifecycle

StageGuard treats an observability-plane outage as a safety state, not as a diagnosis.

## Contract

When a required Grafana MCP/Prometheus/Loki evidence read fails with the adapter-neutral `EvidenceUnavailable` contract:

1. The investigator returns `status="abstain"` with `confidence=0.0` and no hypothesis.
2. `unavailable_evidence` identifies only the bounded semantic slot (for example `causal` or `causal_log`).
3. `missing_evidence` remains reserved for successful evidence queries that returned no authoritative sample.
4. Raw adapter/provider exception text is never copied into the incident report, lifecycle API, audit timeline, or operator DOM.
5. Evidence collection stops at the first required unavailable slot; partial evidence cannot become a diagnosis.
6. `IncidentService.briefing()` rejects evidence-unavailable reports before invoking Gemini. This is a server-side lifecycle rule, not only a browser affordance.
7. `IncidentService.approve()` rejects every report whose status is not `diagnosed` before creating an approval record.
8. No remediation provider call is possible without a valid diagnosed report and exact revision-bound approval.

## Operator/API semantics

The authenticated incident API serializes `IncidentReport.to_dict()`, so clients receive both `missing_evidence` and `unavailable_evidence`. Consumers must render these differently:

- `missing_evidence`: query succeeded, but authoritative telemetry was absent.
- `unavailable_evidence`: StageGuard could not safely obtain required evidence from the observability plane.

The same-origin operator cockpit renders `unavailable_evidence` as an explicit **Evidence plane unavailable** card and connection state. It deliberately uses fixed safety copy rather than provider exception text. Semantic slot names are passed through a fixed allowlist before they are turned into human-readable labels; unknown values are not copied into the DOM.

For an evidence-unavailable incident:

- the displayed root cause is `Not established`;
- confidence is presented as abstained/zero rather than as a weak diagnosis;
- Gemini briefing is disabled in the browser **and** refused by `IncidentService` if a caller bypasses the UI;
- revision entry for approval is disabled;
- approval remains disabled;
- execution remains disabled;
- the operator is instructed to restore observability and run a fresh investigation.

The briefing refusal happens before model invocation and does not create `briefing_generated` or `briefing_failed` audit events. An observability outage is deterministic lifecycle state; it is not a condition that should be sent to an advisory model that lacks provider-failure detail.

The authenticated `POST /v1/briefing` route preserves the same invariant for non-browser callers. It returns the bounded lifecycle rejection through the API error envelope, keeps `Cache-Control: no-store`, does not invoke Gemini, does not mutate the audit timeline, and does not expose the underlying evidence-provider exception text.

The authenticated mutation routes preserve the same fail-closed boundary for non-browser callers. `POST /v1/approve` rejects an evidence-unavailable abstention because it is not diagnosed, and `POST /v1/execute` then rejects because no explicit approval exists. Both rejections keep `Cache-Control: no-store`, create no remediation audit events, make no remediation-provider call, and do not expose provider exception text. A follow-up `GET /v1/incident` must still show the original abstained revision with no approval or outcome.

A fresh diagnosed revision is required before any approval or execution affordance can become available again. Existing partial evidence never becomes authorization material.

## Audit semantics

`investigation_completed` remains the lifecycle event for an unavailable evidence plane and records the bounded status (`abstain`), confidence, revision, and evidence mode. Provider errors, tokens, endpoints, query text, and exception bodies are excluded from the public timeline.

Approval rejection is intentionally not recorded as `remediation_approved`; a rejected approval attempt must leave the incident snapshot without an approval and must not call the remediation adapter.

A rejected evidence-unavailable briefing is likewise not recorded as a model failure because Gemini is intentionally never invoked. This keeps the audit trail semantically accurate: an evidence-plane outage is not a Gemini/provider error.

## Regression coverage

`runtime/tests/test_evidence_unavailable_lifecycle.py` covers:

- sanitized service/API propagation of `unavailable_evidence`;
- strict separation from `missing_evidence`;
- first-failure collection stopping;
- audit sanitization;
- server-side Gemini briefing rejection before model invocation and without briefing audit events;
- approval rejection before any approval audit record;
- zero remediation-provider calls after rejected approval.

`runtime/tests/test_api_evidence_unavailable_briefing.py` exercises the actual authenticated HTTP server and covers:

- `POST /v1/investigate` producing a sanitized evidence-unavailable abstention;
- direct authenticated `POST /v1/briefing` rejection for that exact incident revision;
- zero Gemini invocations despite bypassing the browser;
- no new audit event and no remediation-provider call;
- `Cache-Control: no-store` on the rejected response;
- absence of injected provider-detail and endpoint sentinels from both investigation and briefing response bodies.

`runtime/tests/test_api_evidence_unavailable_mutations.py` exercises the actual authenticated HTTP mutation boundary and covers:

- direct authenticated `POST /v1/approve` rejection for an evidence-unavailable abstention;
- direct authenticated `POST /v1/execute` rejection with no approval present;
- zero Gemini and remediation-provider calls;
- an unchanged audit log containing only `investigation_completed`;
- `Cache-Control: no-store` on both rejected mutation responses;
- absence of injected provider-detail and endpoint sentinels from mutation and incident responses;
- a final `GET /v1/incident` proving the abstained revision remains unchanged with no approval or outcome.

`runtime/tests/test_operator_console.py` additionally covers the browser safety boundary:

- the dedicated evidence-plane-unavailable safety card exists;
- the UI detects only the bounded abstain + `unavailable_evidence` state;
- briefing and approval inputs are disabled unless the current report is diagnosed;
- execution requires a diagnosed report in addition to an approval;
- semantic evidence slots are converted through an allowlist rather than rendered raw;
- provider URLs, operation IDs, and raw unavailable slot joins are absent from the operator asset.
