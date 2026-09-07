# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable production path now covers:

`strict telemetry mapping → metric/Loki activation pins → official Grafana MCP evidence → deterministic diagnosis + Loki corroboration → authenticated IncidentService → optional revision-bound Gemini briefing → approval-gated remediation → telemetry recovery verification → bounded durable audit → Cloud Run/IAP deployment → independent liveness/readiness → bounded readiness cache/backoff + self-observability → authenticated same-origin operator cockpit → bounded redacted incident timeline → narrowly scoped durable Cloud Logging timeline reconstruction`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Production Prometheus and Loki datasource identities and semantic contracts are pinned by expiring activation artifacts.
- Activation freshness and contract/datasource pins are revalidated locally on every readiness request.
- External Grafana MCP readiness probes are bounded and cached so frequent health polling cannot stampede Grafana.
- A previous external success may be reported as `stale` only within a short fixed grace window after a transient refresh failure; once that window expires StageGuard becomes unready.
- A local activation failure is never masked by cached or stale external reachability.
- Gemini remains advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Operator UI requests are same-origin and server-authoritative; the browser receives no Grafana, Gemini, remediation, Cloud Logging, or infrastructure credential.
- Human approval remains bound to the exact incident evidence revision; the cockpit adds explicit typed-revision confirmation without weakening server-side enforcement.
- Operator audit reads are incident-scoped, bounded, schema-pinned, and redacted; the browser never receives generic Cloud Logging read access or arbitrary filter capability.
- Production writes remain disabled in the standard Cloud Run composition.
- `/healthz` proves process liveness only; `/readyz` proves the bounded evidence plane; `/metrics` exposes fixed non-sensitive readiness telemetry.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP integration with datasource/Prometheus/Loki read tools and writes/proxied tools disabled.
- Deterministic incident investigation and bounded Loki corroboration.
- Strict configurable telemetry mapping, metric preflight, Loki preflight, and expiring activation pins.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport.
- Bounded revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity provider and bounded Google Cloud Logging audit sink.
- Dedicated non-root Cloud Run image with embedded official Grafana MCP binary and remediation disabled.
- `/healthz` liveness + fail-closed `/readyz` using read-only MCP `get_datasource` checks.
- Persistent readiness probe with external-probe TTL, failure backoff, bounded stale-on-transient-failure semantics, single-flight locking, and Prometheus-format self-observability.
- Authenticated same-origin operator cockpit for deterministic evidence, Gemini briefing, revision-bound approval, execution, and recovery state.
- Bounded incident-scoped audit timeline with sequence pagination, actor pseudonymization, event-specific payload allow-lists, and same-origin cockpit rendering.
- Production Cloud Logging audit reader pinned to the dedicated StageGuard log, `stageguard.audit.v1`, one exact incident ID, a bounded lookback, and a bounded result count; durable and in-process timeline entries are merged by sequence before the same UI redaction allow-list is applied.

## Run log — 2026-09-07 — durable audit timeline reconstruction

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected the current repository and the implementation surfaces most relevant to the previous handoff:

- `runtime/cloud_audit.py`
- `runtime/incident_service.py`
- `runtime/bootstrap.py`
- `runtime/cloudrun_entrypoint.py`
- `runtime/api.py`
- `runtime/tests/test_audit_timeline.py`
- `runtime/requirements-cloudrun.txt`
- `Dockerfile.api`
- `OPERATOR_CONSOLE.md`

The highest-value unblocked gap was the previous handoff: Cloud Logging was already the durable sink of record, but the operator timeline could read only the current process-local projection.

### Research / attribution checked

Verified the current official Google Cloud Logging Python client documentation before implementing the reader. `Logger.list_entries()` supports server-side `filter_`, ordering, `max_results`, and `page_size`, which allows StageGuard to keep the provider query bounded rather than downloading broad log history and filtering it in-process:

- https://docs.cloud.google.com/python/docs/reference/logging/latest/logger
- https://docs.cloud.google.com/python/docs/reference/logging/latest/client

Google's current Cloud Logging documentation also distinguishes log-write and log-read permissions; StageGuard continues to keep those capabilities server-side and does not expose a Logs Explorer-style surface to the browser.

### Exact changes made

Added `runtime/durable_audit_reader.py`:

- introduced `GoogleCloudAuditReader` as a narrow read adapter rather than a generic Cloud Logging proxy;
- binds every provider query to the configured logger's fully qualified `logName`;
- requires `jsonPayload.schema="stageguard.audit.v1"`;
- filters one exact `incident_id` and `jsonPayload.sequence > after_sequence`;
- applies a default 24-hour lookback with a hard seven-day implementation ceiling;
- caps one provider read at 101 entries so the service can request at most one look-ahead row for pagination;
- uses ascending provider ordering and then deterministically sorts by audit sequence;
- rejects blank/oversized incident IDs and escapes Logging filter literals;
- requires the exact audit-v1 top-level document shape and rejects unknown top-level fields;
- reuses the existing `audit_event_document()` validator so read-path payload constraints cannot be broader than write-path constraints;
- rejects wrong-incident entries, old/future timestamps, lower-bound sequence violations, and conflicting duplicate sequences;
- imports `google-cloud-logging` lazily so local/free development remains credential- and dependency-light.

Updated `runtime/incident_service.py`:

- added an optional `AuditReader` protocol and constructor dependency;
- `audit_timeline()` now asks the durable reader for at most `limit + 1` entries when configured;
- durable and process-local events are merged by sequence;
- identical duplicate events are deduplicated;
- conflicting events claiming the same sequence fail closed;
- the existing event-type-specific `_timeline_event()` allow-list remains the only data promoted to the operator response;
- current-incident binding, 1..100 response bounds, actor pseudonymization, and sequence pagination remain unchanged.

Updated `runtime/bootstrap.py`:

- Cloud Logging mode now constructs both `GoogleCloudLoggingAuditSink` and `GoogleCloudAuditReader` against the same configured project/log name;
- the durable reader is injected into `IncidentService` only for the `cloud-logging` backend;
- JSONL/local development keeps `audit_reader=None` and therefore retains the existing free/process-local behavior;
- production remediation defaults and credential boundaries were not changed.

Added and hardened `runtime/tests/test_durable_audit_reader.py`:

- fake logger verifies the exact dedicated `logName` filter;
- verifies audit-v1 schema, incident, sequence, time-window, ordering, `max_results`, and `page_size` bounds;
- verifies wrong incident, unknown document fields, unsafe cursors/result counts, old/future entries, and conflicting duplicate sequences are rejected;
- verifies durable/local timeline merging still applies the existing payload redaction allow-list;
- verifies a conflicting durable/local sequence fails closed.

Updated `OPERATOR_CONSOLE.md`:

- documents the durable reader contract and exact bounds;
- makes explicit that `/v1/audit` accepts no arbitrary Cloud Logging filters, resource names, log names, time ranges, or query expressions;
- documents the production durable/local merge and unchanged browser redaction boundary;
- documents that JSONL/local development still requires no Cloud Logging read capability;
- explicitly records the remaining limitation: durable audit reconstruction does not yet restore the complete incident state machine after a cold restart.

### Commits produced this run

- `08fedd76` — add bounded durable audit reader
- `ab8cf407` — merge durable audit history into the operator timeline
- `0161b30e` — wire durable audit reader into the Cloud Logging runtime
- `e498bae9` — add durable audit reader contract tests
- `8b111ba7` — pin durable reads to the dedicated fully qualified StageGuard log
- `a194ff94` — harden durable reader/merge tests
- `37d152be` — document durable operator audit reads

### Tests / checks / results

Attempted a clean checkout and targeted suite with:

`PYTHONPATH=runtime python -m unittest runtime.tests.test_durable_audit_reader runtime.tests.test_audit_timeline -v`

The local execution container again failed before Python started because DNS resolution for `github.com` is unavailable:

`fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com`

Therefore the new tests are **not claimed as passing** in this runtime. No GitHub Actions workflow was created, triggered, rerun, or used as a workaround.

No Grafana, Loki, Gemini, IAP, Cloud Logging, Secret Manager, operator, or remediation credential was used. No production Cloud Run or Grafana resource was changed.

### Decisions made

1. **Keep the durable reader narrower than Logs Explorer.** The browser cannot choose a log, filter, resource, time window, or provider query.
2. **Pin the dedicated log explicitly.** Relying only on schema/incident fields would be unnecessarily broad even though the configured logger is already logically scoped.
3. **Reuse the write validator on reads.** Durable data is treated as untrusted input and must satisfy the same bounded audit-v1 contract before it reaches the service.
4. **Keep UI redaction after durable/local merge.** Cloud Logging history never bypasses the event-specific allow-list or actor pseudonymization.
5. **Use one-row look-ahead pagination.** The provider can return at most 101 entries for an API page capped at 100, enough to determine `has_more` without an unbounded read.
6. **Keep local/free development unchanged.** The JSONL backend gets no Cloud Logging reader and needs no Google credential.
7. **Do not confuse audit reconstruction with lifecycle restoration.** The operator can recover bounded durable provenance for the exact current incident, but StageGuard does not yet reconstruct the complete `IncidentSnapshot`, approval, or recovery state after a cold process restart.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted because the local execution environment cannot resolve `github.com` for a runnable checkout.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- The durable reader has fake-client coverage but has not yet been exercised against a real Cloud Logging project/service account.
- The cockpit has not yet been exercised through a real Cloud Run + IAP browser session.
- Cache/stale readiness behavior has not yet been exercised against a real `mcp-grafana:1.3.0` + Grafana Cloud/self-hosted instance.
- Optional Gemini has not yet been exercised against live Vertex AI ADC.
- Cloud Logging reconstruction currently supplements the timeline for an active in-memory incident; it does not restore the incident state machine after a cold restart.

## Single best next step

**Make the incident lifecycle itself restart-safe, not just its audit timeline: add a bounded versioned incident-checkpoint abstraction with a credential-free local implementation and an optional Google Cloud persistence adapter, persist only the minimum server-side state required to restore the current `IncidentSnapshot`/revision/approval-consumption boundary, integrity-check the checkpoint before use, keep raw Grafana/Gemini/remediation credentials out of it, and add crash/restart tests proving stale approvals can never be replayed against a different evidence revision.**
