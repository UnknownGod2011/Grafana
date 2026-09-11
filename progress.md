# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The working vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, deployment hardening, watchdog observability, authenticated Cloud Run metrics ingestion, stale/scrape health detection, credential-free outage rehearsal, pinned Grafana/Prometheus acceptance images, runtime-version attestation, strict Prometheus acceptance parsing, cardinality ambiguity rejection, fail-closed MCP parsing, and now structured evidence-unavailable abstention at the incident orchestration boundary.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, nonnumeric, or non-finite Prometheus evidence must never be interpreted as healthy incident evidence.
- Expected evidence-plane transport/protocol failures must become a sanitized abstention, not an opaque request failure and not a diagnosis.
- Programming/configuration defects must remain visible exceptions rather than being disguised as evidence unavailability.
- Partial or unavailable evidence must never reach infrastructure mutation.

## Run log — 2026-09-11 — structured evidence-unavailable orchestration

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the current default branch and the relevant evidence/lifecycle path, including:
- `runtime/investigator.py`
- `runtime/mcp_metric_client.py`
- `runtime/mcp_log_client.py`
- `runtime/mcp_smoke.py`
- `runtime/incident_service.py`
- `runtime/remediation.py`
- `runtime/tests/test_investigator.py`
- `runtime/tests/test_correlated_investigator.py`
- `runtime/tests/test_mcp_metric_client.py`
- `runtime/tests/test_remediation.py`
- `docs/grafana-mcp-evidence-safety.md`

The previous single best next step was to convert expected Grafana MCP transport/protocol failures into a structured `abstain`/evidence-unavailable outcome while preserving programming failures and preventing partial evidence from reaching remediation. This run implemented that boundary.

### Exact changes made

#### Added adapter-neutral evidence availability contract

Created `runtime/evidence_errors.py` with `EvidenceUnavailable`. The contract is intentionally small: adapters use it only for expected evidence-source availability/integrity failures. Investigator code can catch this contract without importing Grafana-MCP-specific exception types.

Commit:
- `a2cf86f82fe32ae699febc3dd83dd484cf3ebb6c` — add adapter-neutral evidence availability contract

#### Classified Grafana MCP metric failures

Updated `runtime/mcp_metric_client.py` so `McpMetricError` also implements `EvidenceUnavailable`.

Changes include:
- MCP tool errors no longer copy raw provider/tool content into exception text;
- malformed/non-finite/ambiguous metric results remain explicit fail-closed errors;
- MCP process startup `OSError`/`FileNotFoundError`, stdio failures such as broken pipes, and `McpError` protocol failures are translated to sanitized `McpMetricError`;
- invalid caller inputs such as blank PromQL/datasource UID remain `ValueError` and are not converted into evidence availability failures.

Commits:
- `18babd109731e51c46920be6041d9d685557964c`
- `29314eafc4e784918ea870d3c16f60e9878bc4a9`

#### Classified Grafana MCP Loki failures

Updated `runtime/mcp_log_client.py` similarly:
- `McpLogError` implements `EvidenceUnavailable`;
- raw MCP tool error content is not copied into the exception message;
- process startup/stdio/protocol availability failures are translated into sanitized evidence-source failures;
- malformed Loki data still fails closed;
- blank LogQL and invalid bounds remain programming/configuration errors.

Commits:
- `c8ee8cad4b051dcfb3039361f91bcbf8c23f64a1`
- `12b2bd447c9581e64c869810856f08094a11c8ef`

#### Added structured abstention in the bounded investigator

Updated `runtime/investigator.py`:
- `IncidentReport` now exposes `unavailable_evidence` separately from `missing_evidence`;
- metric collection is performed in the fixed semantic-slot order and stops at the first `EvidenceUnavailable` failure;
- the returned report is `status="abstain"`, `hypothesis=None`, `confidence=0.0`;
- only the semantic slot name is preserved, e.g. `causal`; adapter exception text is never copied into the report;
- successful empty-vector telemetry continues to use `missing_evidence`, preserving the distinction between "query succeeded but no sample exists" and "evidence source could not safely answer";
- Loki transport/protocol failure after a metric diagnosis produces the same structured abstention with `unavailable_evidence=("causal_log",)`;
- arbitrary exceptions are deliberately not caught.

Commit:
- `14b6194d193d33dada9a8c83c19741b3a59768ea`

#### Added fail-closed regressions

Updated `runtime/tests/test_investigator.py`:
- evidence-source failure yields sanitized abstention;
- the failed slot is preserved;
- exception secrets do not enter `summary` or `to_dict()`;
- collection stops at the failure rather than continuing unnecessary evidence reads;
- a `TypeError` from an adapter continues to propagate.

Updated `runtime/tests/test_correlated_investigator.py`:
- Loki evidence-source failure converts a metric diagnosis into a sanitized abstention;
- `causal_log` is preserved as the unavailable semantic slot;
- arbitrary Loki programming errors still propagate.

Updated `runtime/tests/test_remediation.py`:
- an evidence-unavailable abstention cannot execute remediation even when handed an otherwise matching explicit approval; the remediation adapter receives zero calls.

Commits:
- `031406ebe110a7c890b6e6a603f9748f225250c1`
- `225a35b633a7d70f2e91542bfc1aebc9d4620748`
- `c36327dac1d7787019cbd5489aeeaca954056b7b`

#### Updated evidence-safety documentation

Expanded `docs/grafana-mcp-evidence-safety.md` to document:
- the adapter-neutral availability contract;
- the exact difference between `missing_evidence` and `unavailable_evidence`;
- sanitization requirements;
- first-failure collection stopping;
- programming-error propagation;
- the remediation gate that requires `status == "diagnosed"`.

Commit:
- `5bebf97679caaacd859790b602aab59c95a4dd96`

### Checks / results

Attempted a clean executable checkout and focused unit set:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
python -m unittest \
  runtime.tests.test_investigator \
  runtime.tests.test_correlated_investigator \
  runtime.tests.test_mcp_metric_client \
  runtime.tests.test_mcp_log_client \
  runtime.tests.test_remediation
```

The container again failed before checkout with `Could not resolve host: github.com`. Therefore no green unit-test claim is made for this run.

Static reasoning checks performed while editing:
- `McpMetricError` and `McpLogError` are subclasses of the adapter-neutral `EvidenceUnavailable` contract;
- the investigator catches only that contract, not `Exception`;
- remediation already requires `report.status == "diagnosed"`, so the new abstention cannot pass `_approval_matches`;
- no GitHub Actions workflow was created, changed, triggered, or rerun;
- no Grafana Cloud, GCP/IAM/Cloud Run, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Keep evidence availability distinct from evidence absence. `None`/`missing_evidence` means a successful bounded query produced no authoritative sample; `unavailable_evidence` means the evidence plane could not safely answer.
2. Sanitize at two layers: MCP adapters do not embed raw tool/provider content in operational errors, and investigator reports never copy adapter exception messages.
3. Stop metric evidence collection at the first unavailable required slot. A degraded evidence plane should not cause additional unnecessary reads, and partial evidence cannot become a diagnosis.
4. Catch only an explicit evidence-availability contract. `TypeError`, `AssertionError`, invalid policy input, and other defects must stay visible.
5. Preserve the existing remediation invariant: only a fully `diagnosed` report can match an approval and mutate infrastructure.

### Blockers / unknowns

- The focused unit set above still needs execution from a runnable checkout.
- The complete credential-free Docker watchdog rehearsal still needs to run against pinned Prometheus 3.13.3 and Grafana 13.2.1.
- The authenticated metrics bridge still needs a disposable-project acceptance against a private Cloud Run StageGuard service using a least-privilege invoker identity.
- Container image digests remain uncommitted because authoritative registry digests have not been verified through the available execution path.
- The historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**Carry the new `unavailable_evidence` state through `IncidentService` and the authenticated API/operator UI as a first-class operational condition: regression-test that an evidence-plane failure produces an auditable investigation-completed abstention, that the approval endpoint/service refuses it before creating an approval record, and that the UI clearly distinguishes `evidence unavailable` from ordinary `missing telemetry` without surfacing adapter/provider secrets. If a runnable checkout becomes available first, execute the focused unit set above before further integration work.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the newest ordered scrape/stale outage acceptance path, explicit image pins, runtime-version attestation, strict Prometheus safety parsing, live ambiguity probe, bridge readiness work, and current evidence-unavailable orchestration.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the current MCP evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
