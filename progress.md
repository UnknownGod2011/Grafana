# StageGuard Progress

## Current status

StageGuard is an implementation-ready product/architecture specification for the Grafana track of Google Cloud Agentic Cinema.

**Current implementation gate:** prove the smallest real runtime slice using hackathon-permitted tooling:

`Gemini/ADK → official Grafana MCP → seeded live-production telemetry → evidence-grounded diagnosis`

Do not build broad UI or multiple scenarios before this works.

Core handoff documents now exist:

- `README.md` — product thesis, user experience, sponsor dependency, safety and MVP
- `ARCHITECTURE.md` — system boundaries, telemetry/evidence model, deployment and remediation architecture
- `DEMO.md` — deterministic 3-minute judge narrative
- `VERTICAL_SLICE_SPEC.md` — fixed `broadcast-alpha` Gate A/B/C contract
- `INTEGRATION_HANDOFF.md` — MCP deployment decision, auth/transport posture, judge evidence package, real-user onboarding and production evolution

---

## Run log — 2026-09-06 — initial specification

### Meaningful progress

Initialized the previously empty repository with README, architecture, demo and persistent progress specifications.

### Decisions locked

1. Primary use case is live production/broadcast incident response, not generic SRE.
2. Primary demo failure is Camera 3 frame drops caused by `uplink-b` packet loss.
3. Grafana is the operational evidence source before and after remediation.
4. Grafana investigation and remediation are separated; StageGuard does not get arbitrary shell/cloud access.
5. Rerouting a live feed is human-approved in the demo.
6. Resolution requires Grafana telemetry verification.
7. UX is an incident cockpit, not chatbot-first.
8. Adoption path is investigation-only → recommendations → human-approved actions → selective autonomy.
9. One excellent vertical slice comes before additional failure types.

---

## Run log — 2026-09-06 — vertical slice contract

### Inspected at start

Read `progress.md`, `README.md`, and `ARCHITECTURE.md`. The highest-priority ambiguity was the exact sponsor-runtime acceptance contract.

### Meaningful progress

Created `VERTICAL_SLICE_SPEC.md`, freezing:

- `broadcast-alpha` topology
- `cam-1`, `cam-2`, `cam-3`, `uplink-a`, `uplink-b`, `program-out`
- packet-loss ground truth
- minimum Prometheus metric contract
- optional Loki corroboration
- bounded evidence sequence
- conceptual PromQL and expected results
- structured diagnosis fields
- evidence/confidence thresholds and `INCONCLUSIVE` behavior
- minimum Grafana MCP tool/RBAC posture
- Gate A: sponsor-runtime diagnosis proof
- Gate B: judge-ready investigation
- Gate C: approval/remediation/verification

### Decisions locked

1. Gate A is diagnosis-only.
2. High confidence requires symptom + causal + contradiction + healthy-peer evidence.
3. Hard-coded diagnosis fails Gate A.
4. Prometheus is the minimum data path; Loki cannot block initial connectivity.
5. P0 MCP is least-privilege/read-side only.
6. `run_panel_query` is optional judge-facing polish, not a Gate A dependency.
7. Actual deployed tool names/payloads/permissions must be recorded from runtime evidence.

---

## Run log — 2026-09-06 — integration/onboarding handoff

### Inspected at start

Read `progress.md`, `README.md`, and `VERTICAL_SLICE_SPEC.md`. The largest remaining specification ambiguity was **which Grafana MCP mode should be attempted first and how the hackathon proof evolves into a real-user connection flow**.

### Fresh official research checked 2026-09-06

Verified current Grafana documentation:

1. **Grafana Cloud MCP** is hosted, uses OAuth 2.1, uses Streamable HTTP, inherits user-scoped RBAC, and allows read-only authorization without write permissions.
2. Cloud MCP is part of Grafana Assistant; connected users count toward Assistant usage, so StageGuard should not silently provision/enable potentially billable provider capabilities.
3. **OSS `grafana/mcp-grafana`** can run with a dedicated service-account token and supports local deployment paths including Docker; official docs cover stdio and HTTP transports.
4. Grafana MCP exposes per-tool RBAC requirements, enabling datasource-scoped least privilege.
5. Grafana MCP Observability can show session health, tool usage, latency/failures and transport behavior.
6. OSS MCP can expose Prometheus metrics over HTTP transports and export traces/logs with OpenTelemetry.

Official references are recorded in `INTEGRATION_HANDOFF.md`.

### New file: `INTEGRATION_HANDOFF.md`

This run adds the operational handoff needed before permitted implementation:

- recommends official OSS `mcp-grafana` first for the deterministic/no-new-billing Gate A proof
- positions hosted Grafana Cloud MCP as the preferred lower-friction real-user onboarding path where available
- defines local stdio vs separated-service Streamable HTTP decision
- specifies least-privilege service-account posture
- defines a judge-proof evidence ledger showing actual MCP tool calls/data queries without exposing chain-of-thought
- defines the exact compact Gate A judge card
- defines two onboarding flows: Grafana Cloud OAuth and self-hosted/OSS MCP
- defines readiness tests before calling a customer connection usable
- introduces a telemetry mapping model so real users do **not** have to rename their existing vendor metrics to StageGuard demo metric names
- preserves the evidence-plane/action-plane security separation
- defines the Grafana “double reveal”: StageGuard observes the broadcast through Grafana; Grafana observes StageGuard's MCP behavior
- adds an implementation evidence checklist to populate from actual runtime behavior

### Decisions locked this run

1. **First implementation preference: official OSS `grafana/mcp-grafana`**, unless the permitted Gemini environment makes hosted Cloud MCP materially simpler without enabling new billing.
2. **Do not auto-enable paid/provider usage.** Users connect an existing environment and StageGuard discloses provider-side usage implications.
3. **Real production onboarding must support existing telemetry through mappings**, rather than demanding StageGuard-specific metric names.
4. **Judge-visible agent traces show tool actions/evidence, not hidden chain-of-thought.**
5. **Grafana stays the evidence plane; remediation credentials stay in a separate, narrowly scoped action adapter.**
6. Grafana MCP/agent observability is a closing sponsor showcase after Gate B/C, not an eligibility dependency.

### Why this is meaningful progress

The permitted implementation session no longer needs to decide between an opaque “Grafana connection” and several conflicting deployment/auth models. It has a safe first path, a production onboarding path, a concrete judge evidence format, and a compatibility strategy for real customers' existing metrics.

---

## Current blockers / unknowns

1. **No submitted implementation exists yet.** This remains intentional under the hackathon's stated AI-tool restrictions; implementation should use Gemini CLI/Gemini Code Assist / permitted Google tooling.
2. **No Grafana environment is provisioned/connected yet.** First preference is OSS MCP + a controlled Grafana instance for Gate A.
3. **Google Cloud/Gemini runtime is not connected yet.**
4. **No deterministic telemetry simulator exists yet.** Its first scenario is fully specified.
5. **No Grafana dashboards/alerts/data sources exist yet.**
6. **No remediation adapter exists yet.** It must wait until Gate B passes.
7. **No LICENSE file exists.** Official submission requires a visible open-source license; license choice remains uncommitted.
8. **Hosted project URL and demo assets do not exist yet.**
9. **Actual runtime MCP tool names/request/result payloads remain unknown until implementation.** Runtime evidence overrides documentation assumptions.

## Risks to watch

- sponsor integration becomes cosmetic
- UI polish precedes MCP connectivity
- plausible diagnosis is returned without enough evidence
- broad permissions are granted for convenience
- Cloud MCP usage is enabled without user awareness of provider-side usage/billing implications
- real-user adoption depends on renaming all existing telemetry
- remediation is coupled to Grafana credentials
- recovery is claimed from an action response rather than observed telemetry
- optional AI/MCP Observability distracts from required core MCP use
- demo depends on nondeterministic external failures

---

## Single best next step

**Using hackathon-permitted Google tooling, execute Gate A with the recommended OSS-first path:**

1. seed `broadcast-alpha` Prometheus telemetry
2. connect it to a controlled Grafana instance
3. run official `grafana/mcp-grafana` with a dedicated datasource-scoped read/query identity
4. connect the permitted Gemini/ADK runtime
5. retrieve all four evidence classes
6. diagnose `uplink-b` packet loss and explicitly reject encoder overload
7. record the actual environment, MCP version/mode/transport, auth/RBAC posture, datasource identifiers, tool names, query payload/result shapes, tool-call count, latency and reproducibility result in the repo

**Do not build UI or remediation before this passes.**
