# StageGuard Operations & Safety Contract

This document turns StageGuard from a hackathon demo into a deployable operating model for live media teams. It is intentionally implementation-facing but contains no submitted application code.

## 1. Product operating modes

StageGuard must support four explicit modes. A deployment always has exactly one active mode.

| Mode | Grafana access | Remediation access | Intended use |
|---|---|---|---|
| Observe | read/query only | none | onboarding, audit, shadow mode |
| Recommend | read/query only | none | root-cause + suggested operator action |
| Approve-to-act | read/query only | allowlisted action adapter | production default for consequential actions |
| Selective autonomy | read/query only | allowlisted reversible actions | mature deployments after evaluation |

The hackathon demo should use **Approve-to-act**.

## 2. Hard security boundary

Grafana is the **evidence plane**, not the action plane.

StageGuard's Grafana identity must not carry credentials for routers, encoders, cloud consoles, Kubernetes clusters, SSH, or shell execution. Remediation is performed by a separate adapter with its own narrowly scoped credential and an allowlist of actions.

Required properties:

- Grafana MCP is read/query scoped for the MVP.
- MCP write tools are disabled for Gate A/B unless a later, justified feature explicitly requires them.
- Datasource access is limited to the exact Prometheus/Loki datasource UIDs needed for the production.
- Remediation credentials are never sent to Grafana MCP or exposed to the LLM.
- Every action request has an action ID, target, reason, evidence references, requester, approval state, execution result, and verification result.
- No arbitrary command execution exists in the product contract.

## 3. Minimum Grafana permission profile

For the first production-grade slice, target the smallest possible profile:

- `datasources:query` on the selected Prometheus datasource UID
- `datasources:query` on the selected Loki datasource UID when logs are enabled
- optional `dashboards:read` on only the StageGuard/operator dashboard UID
- no dashboard write
- no alert-rule write
- no incident write
- no admin/team/user permissions

Run the OSS MCP server with write operations disabled. Query execution must remain enabled because `query_prometheus` and, when configured, `query_loki_logs` are core evidence tools.

Do not use a broad Editor role for the final demo if datasource-scoped permissions are available.

## 4. Canonical onboarding flow

A real customer should be able to connect StageGuard without renaming telemetry or rebuilding dashboards.

### Step 1 — Connect Grafana

Choose one:

1. **Grafana Cloud MCP**: user-authorized OAuth connection where available.
2. **Self-hosted / OSS MCP**: customer provides a dedicated least-privilege service-account token to the deployed StageGuard environment.

Secrets are stored in the deployment secret manager, never committed to the repo.

### Step 2 — Select production scope

User chooses:

- organization/workspace
- Prometheus datasource
- optional Loki datasource
- optional existing production dashboard
- production identifier(s) to monitor

StageGuard must not query unrelated organizations or datasources.

### Step 3 — Map telemetry

StageGuard uses a canonical logical model while accepting existing metric names.

Minimum logical signals for the hero scenario:

| Canonical signal | Example source mapping |
|---|---|
| feed frame-drop rate | customer's encoder/drop metric |
| encoder CPU/GPU health | customer's host/encoder metric |
| uplink packet loss | customer's network metric |
| uplink latency | customer's RTT/latency metric |
| feed-to-uplink relation | static mapping or labels |
| peer feed health | same mapped feed metrics filtered by peer |

Mappings are configuration, not hard-coded assumptions.

### Step 4 — Readiness test

A connection is not considered usable until StageGuard can prove:

1. datasource connectivity
2. permission to execute required read queries
3. all required logical signals resolve to non-empty data
4. production label/filter resolves only the intended environment
5. timestamps are sufficiently fresh
6. a healthy-baseline query works
7. no write-capable MCP operation is required for investigation

The UI should show a simple readiness result: **Ready / Degraded / Not Ready**, plus the failed checks.

### Step 5 — Shadow incident

Before enabling recommendations or actions, run one simulated or historical incident and compare StageGuard's diagnosis against known ground truth.

## 5. Evidence contract

StageGuard must never present a high-confidence root cause without enough observable support.

A high-confidence diagnosis requires four evidence classes:

1. **Symptom evidence** — the user-visible production signal is degraded.
2. **Causal evidence** — a plausible upstream component is abnormal.
3. **Contradiction evidence** — a major alternative hypothesis is measurably healthy.
4. **Peer evidence** — unaffected comparable feeds/components constrain blast radius.

If any required class is unavailable or contradictory, StageGuard returns `INCONCLUSIVE` or reduces confidence rather than inventing certainty.

Each evidence item exposed to the operator should contain:

- evidence ID
- Grafana datasource/tool used
- query time window
- human-readable finding
- affected entity
- observed value / baseline or threshold
- timestamp
- optional dashboard deep-link

Do not expose hidden chain-of-thought. Show tool actions, evidence and decision summaries only.

## 6. Remediation policy contract

Every remediation action is declared before runtime.

Required action metadata:

- `action_id`
- display name
- target resource type
- reversible: yes/no
- impact tier
- required approval tier
- parameter schema
- preconditions
- rollback action if applicable
- verification queries
- timeout

### Demo action

**Reroute `cam-3` from `uplink-b` to `uplink-a`.**

Policy:

- reversible: yes
- approval: mandatory
- precondition: uplink A healthy and below capacity threshold
- execution: synthetic/demo routing adapter only
- verification: re-query frame drops + packet loss after action
- success only if telemetry recovery persists for the defined verification window
- otherwise rollback or mark remediation failed

## 7. Approval UX contract

Approval must show enough context to make the operator responsible, not merely a ceremonial button.

The approval card should contain:

- incident summary
- proposed action
- target
- expected impact
- evidence-backed rationale
- blast radius
- reversibility
- fallback/rollback
- verification plan
- Approve / Reject

An approval expires if underlying evidence becomes stale or the target state changes materially.

## 8. Verification and closure

An action response is not proof of recovery.

StageGuard closes an incident only when Grafana evidence confirms the expected signals have recovered.

For the hero scenario:

1. reroute adapter returns accepted/success
2. wait bounded stabilization interval
3. query uplink-B/cam-3 network symptom path
4. query cam-3 frame-drop signal
5. confirm healthy peer feeds remain healthy
6. if conditions pass, mark `RECOVERED`
7. otherwise mark `ACTION_SUCCEEDED_BUT_NOT_VERIFIED` or `REMEDIATION_FAILED`

## 9. Multi-tenant boundary

For real deployments, tenant isolation must be explicit.

- one customer connection maps to a known Grafana org/workspace
- datasource UIDs are stored per tenant
- production filters are tenant-scoped
- service-account tokens should remain single-organization where possible
- dynamic multi-org mode should not be a default shortcut
- evidence from one tenant must never enter another tenant's incident context

## 10. Judge-visible audit ledger

The demo should show a compact trace such as:

| # | Stage | Tool / action | Evidence / result |
|---|---|---|---|
| 1 | Detect | Grafana alert or operator trigger | `cam-3` frame drops high |
| 2 | Investigate | `query_prometheus` | encoder CPU healthy |
| 3 | Investigate | `query_prometheus` | `uplink-b` packet loss high |
| 4 | Compare | `query_prometheus` | `cam-1` / `cam-2` healthy |
| 5 | Diagnose | Gemini decision summary | likely `uplink-b`; encoder overload rejected |
| 6 | Approve | human approval | reroute approved |
| 7 | Act | remediation adapter | route changed to `uplink-a` |
| 8 | Verify | Grafana queries | frame drops and packet loss recovered |

This is the proof that Grafana is not decorative: the diagnosis and recovery both depend on runtime Grafana evidence.

## 11. Failure behavior

StageGuard must fail safely.

| Failure | Required behavior |
|---|---|
| Grafana unreachable | stop investigation; no remediation |
| query permission denied | surface readiness/permission error; no fallback hallucination |
| required signal missing | mark evidence incomplete / inconclusive |
| stale telemetry | do not treat as current evidence |
| conflicting signals | lower confidence / request operator review |
| remediation adapter unavailable | recommendation-only |
| approval timeout/reject | do not execute |
| action accepted but telemetry not recovered | do not close incident |
| healthy failover path not proven | do not recommend reroute as safe |

## 12. Evaluation gates before selective autonomy

A real deployment should not enable autonomous actions until an evaluation set demonstrates:

- root-cause accuracy meets agreed threshold
- false confident diagnosis rate is acceptably low
- unsafe-action rate is zero in test scenarios
- approval policy is never bypassed
- tenant/data-source isolation holds
- recovery verification is reliable
- missing-data cases result in abstention rather than fabrication

The hackathon submission only needs to demonstrate the controlled, human-approved slice well; broader autonomy is a production evolution.

## 13. Current implementation handoff

The next permitted implementation session should implement none of the broad product until **Gate A** proves:

`Gemini/ADK → official Grafana MCP → seeded Grafana/Prometheus evidence → correct diagnosis`

When Gate A passes, record the actual MCP tool names, request/response shapes, datasource UIDs, auth/RBAC behavior, latency, tool-call count and reproducibility. Runtime evidence overrides this specification when implementation details differ.

## Official references checked 2026-09-06

- Grafana MCP tool/RBAC reference: https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- Enable/disable tools and read-only mode: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/
- Loki query guide: https://grafana.com/docs/grafana/latest/developer-resources/mcp/guides/query-logs-with-loki/
- Run dashboard panel queries: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/guides/run-a-dashboard-panel-query/
- Multi-organization / headers: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/multi-organization-and-headers/
