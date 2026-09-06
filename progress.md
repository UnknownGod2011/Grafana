# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable vertical slice now includes a strict real-production onboarding gate before the existing bounded incident lifecycle:

`versioned telemetry mapping → eight-read read-only preflight → Prometheus/Grafana → official Grafana MCP → bounded six-read investigator → audited IncidentService → trusted operator identity → revision-bound approval → separate remediation adapter → bounded two-read recovery verification`

Core invariants:

- Grafana is the read-only evidence plane; write credentials remain separate.
- Callers never provide raw PromQL, datasource IDs, remediation actions, or targets through the incident API or telemetry mapping file.
- Existing production metric/label names are mapped through validated configuration, not interpolated as raw query fragments.
- Every production mapping must explicitly define all semantic bindings; omitted values never silently fall back to demo scope.
- Activation preflight performs exactly the six investigation reads and two recovery reads and requires one numeric sample for every slot.
- Missing or ambiguous evidence refuses activation; missing runtime evidence causes abstention.
- Approval is tied to the exact evidence revision, single-use, and invalidated by fresh investigation.
- Action success is never recovery; recovery requires consecutive healthy telemetry.
- Operator identity comes from authentication context, not request JSON.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Opt-in pinned official `grafana/mcp-grafana:1.1.0` path with write tools disabled.
- Deterministic four-class incident investigation with exactly six metric reads.
- MCP Prometheus metric adapter with fail-closed result parsing and query provenance.
- Approval-gated remediation with a distinct write boundary and telemetry-only recovery proof.
- Audited incident lifecycle service and narrow authenticated HTTP API.
- Loopback development identity plus explicit static-bearer deployment primitive.
- Configurable validated telemetry mapping across investigation, approval target selection, and recovery verification.
- Strict versioned telemetry-config loader and eight-slot read-only production activation preflight.

## Run log — 2026-09-07 — production telemetry onboarding/preflight

### Inspected at start

Read `progress.md` completely before deciding what to implement. Inspected the current repository through the connected GitHub integration, especially:

- `runtime/telemetry.py`
- `runtime/mcp_metric_client.py`
- `runtime/tests/test_telemetry.py`
- root `README.md`

The previous handoff identified production onboarding/preflight as the highest-value unblocked gap. That remained correct: configurable query generation existed, but there was no safe persisted mapping contract or proof that all semantic telemetry slots actually resolved before StageGuard was activated.

### Exact changes made

Added `runtime/onboarding.py`:

- introduced strict `version: 1` JSON telemetry configuration loading;
- caps local configuration at 64 KiB;
- rejects malformed UTF-8/JSON, non-object structures, unknown top-level fields, unknown profile fields, unsupported versions, wrong field types, and malformed peer arrays;
- requires **every** `TelemetryProfile` field to be explicit so a production config can never silently inherit demo production/feed/uplink defaults;
- continues to rely on `TelemetryProfile` identifier validation and PromQL value escaping for the query construction boundary;
- introduced immutable `PreflightSlot` / `PreflightResult` models;
- `preflight_telemetry()` executes exactly eight semantic reads: all six investigation slots plus both recovery slots;
- records each slot as `ok`, `missing`, or `error` instead of failing the whole report on one unavailable source;
- requires every slot to resolve to exactly one numeric sample before `ready=True`;
- ambiguous multi-series responses remain rejected by `McpPrometheusMetricClient` and are surfaced as failed preflight slots;
- preflight has no remediation/write capability.

Added `runtime/preflight.py`:

- operator CLI that loads the strict mapping and runs it through the existing official-Grafana-MCP metric adapter;
- emits machine-readable JSON readiness results;
- exit code `0` = ready, `2` = configuration/transport setup failure, `3` = valid profile but incomplete/ambiguous evidence.

Added `runtime/telemetry.example.json`:

- complete explicit mapping matching the deterministic local fixture;
- no datasource UID, arbitrary PromQL, credentials, remediation configuration, or secrets are represented in the mapping format.

Added `runtime/tests/test_onboarding.py` with credential-free coverage for:

1. loading a complete versioned profile;
2. rejecting unknown top-level fields;
3. rejecting unknown profile fields such as caller-controlled datasource IDs;
4. rejecting unsupported configuration versions;
5. requiring all eight bounded checks for readiness;
6. refusing activation on one missing semantic slot while still evaluating the remaining checks;
7. surfacing an ambiguous/transport-style query failure per slot while preserving the exact eight-query budget.

Updated root `README.md`:

- documented the onboarding safety boundary, example config, preflight command, result semantics, and exit codes;
- updated the runtime diagram and repository map;
- removed the now-obsolete roadmap item for telemetry mapping and moved the live official-MCP lifecycle gate to the front.

### Tests / checks / results

Attempted a clean checkout and full deterministic suite with:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
python -m py_compile runtime/*.py runtime/tests/*.py
python -m unittest discover -s runtime/tests -v
```

The environment failed before checkout with:

```text
fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com
```

Therefore the new suite is **not claimed as executed/passing** in this runtime. No GitHub Actions workflow was added or triggered merely to compensate, preserving the project's low-noise CI/storage policy.

The implementation itself was written directly through the authenticated GitHub repository connection. No Grafana, Gemini, Google Cloud, or remediation credential was required for these changes.

### Decisions made

1. Production config is strict and complete rather than permissive/defaulting; silent fallback to the demo production is too dangerous for an incident commander.
2. Mapping files define semantic bindings only. Datasource selection stays in the MCP adapter/runtime environment and raw PromQL remains unavailable.
3. Preflight proves evidence **coverage and cardinality**, not incident health. A high metric value can still be valid onboarding evidence; diagnosis owns threshold interpretation.
4. The preflight query budget is derived from the same query builders used by investigation and recovery, preventing onboarding/runtime drift.
5. One broken slot does not stop evaluation of the other seven, giving operators a complete remediation checklist while still refusing activation.
6. Preflight is read-only and structurally cannot perform remediation.

### Current blockers / unknowns

- Full deterministic Python suite has not executed in this automation environment because direct GitHub DNS resolution is unavailable to the execution container.
- Full Compose startup and end-to-end official MCP Gate A remain unverified on a Docker-capable host.
- The eight-read preflight, six-read diagnosis, and two-read recovery loop have not yet been exercised through one live `grafana/mcp-grafana:1.1.0` process here.
- OIDC/IAP integration, Loki corroboration, Gemini explanation/orchestration, operator UI, durable multi-user audit storage, and Google Cloud deployment remain implementation gates.
- The current onboarding preflight checks instant-query cardinality/availability but does not yet persist a signed/hash-pinned activation record tying a running `IncidentService` to the exact profile that passed preflight.

## Single best next step

**Add a fail-closed activation artifact that hashes the exact validated telemetry profile plus datasource identity and records the eight successful preflight slots, then require `IncidentService` startup to consume a matching, non-stale activation record. This prevents a profile from being changed after preflight and turns onboarding readiness into an enforceable runtime safety gate rather than a standalone operator check.**
