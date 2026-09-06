# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable vertical slice now includes an enforceable production activation gate before the existing bounded incident lifecycle:

`versioned telemetry mapping → eight-read read-only preflight → hash-pinned/time-bounded activation artifact → Prometheus/Grafana → official Grafana MCP → bounded six-read investigator → activation-enforced audited IncidentService → trusted operator identity → revision-bound approval → separate remediation adapter → bounded two-read recovery verification`

Core invariants:

- Grafana is the read-only evidence plane; write credentials remain separate.
- Callers never provide raw PromQL, datasource IDs, remediation actions, or targets through the incident API or telemetry mapping file.
- Existing production metric/label names are mapped through validated configuration, not interpolated as raw query fragments.
- Every production mapping must explicitly define all semantic bindings; omitted values never silently fall back to demo scope.
- Activation preflight performs exactly the six investigation reads and two recovery reads and requires one numeric sample for every slot.
- Successful preflight can produce a time-bounded activation artifact binding the complete validated telemetry profile and datasource identity by SHA-256.
- Non-default production profiles cannot construct `IncidentService` without a matching, non-stale activation record; profile/datasource drift fails closed.
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
- SHA-256 pinned, expiring activation artifact enforced for non-demo production profiles.

## Run log — 2026-09-07 — enforceable activation artifact

### Inspected at start

Read `progress.md` completely before deciding what to implement. Inspected the current repository through the connected GitHub integration, especially:

- `runtime/onboarding.py`
- `runtime/preflight.py`
- `runtime/mcp_metric_client.py`
- `runtime/incident_service.py`
- `runtime/telemetry.py`
- `runtime/tests/test_onboarding.py`
- `runtime/tests/test_incident_service.py`
- root `README.md`

The previous handoff identified the gap correctly: onboarding could prove readiness, but nothing prevented a profile or datasource from changing after that proof and before `IncidentService` started.

### Exact changes made

Added `runtime/activation.py`:

- introduced strict versioned `ActivationRecord` persistence;
- canonical SHA-256 of the complete validated `TelemetryProfile`, including production/feed/uplink bindings, peers, metrics, and label keys;
- SHA-256 binding of datasource identity instead of persisting the raw datasource UID in the activation artifact;
- digest of the exact eight successful semantic preflight slots;
- activation can only be created from `ready=True`, exactly-eight-slot, all-`ok` preflight results whose production matches the profile;
- default lifetime is 24 hours with a hard maximum of seven days;
- loader caps activation files at 128 KiB and rejects malformed JSON, unknown/missing fields, unsupported versions, and invalid basic field types;
- runtime verification fails closed on production mismatch, profile drift, datasource drift, future-dated records, stale records, or malformed slot digests.

Updated `runtime/preflight.py`:

- added `--activation-output PATH`;
- added bounded `--ttl-seconds` support;
- a successful eight-slot preflight can now write the activation artifact using the datasource UID actually configured in `McpPrometheusMetricClient`;
- failed/incomplete preflight does not create a usable activation artifact;
- machine-readable output includes activation metadata when an artifact is written.

Updated `runtime/incident_service.py`:

- any non-default telemetry profile now requires a matching `ActivationRecord` and datasource identity at construction time;
- stale or mismatched activation prevents service startup before investigation or remediation is possible;
- the built-in deterministic default profile remains an explicit local-demo exception so credential-free fixture development remains usable;
- if the demo profile is supplied with an activation record, that record is still verified rather than ignored;
- investigation audit events include activation profile/datasource hashes when production activation is present, preserving provenance without recording the raw datasource UID.

Added `runtime/tests/test_activation.py` with credential-free coverage for:

1. successful activation creation + file round-trip + verification;
2. refusal to activate failed preflight;
3. telemetry-profile drift rejection;
4. datasource drift rejection;
5. stale activation rejection;
6. non-default `IncidentService` refusing startup without activation;
7. non-default `IncidentService` accepting a matching fresh activation.

Updated root `README.md`:

- added the activation artifact to the runtime diagram and safety model;
- documented the `--activation-output` and TTL workflow;
- documented that production `IncidentService` startup is activation-enforced;
- clarified that the hash-pinned file prevents configuration drift but is not a digital signature or substitute for host/file-integrity controls;
- updated repository map, deployment guidance, roadmap, and project status.

### Tests / checks / results

The new `runtime/activation.py` source was syntax-compiled before repository write in the execution environment.

A complete repository checkout and full deterministic suite still cannot be executed from the available execution container because direct `github.com` DNS resolution has been unavailable in prior attempts. Repository inspection and writes succeeded through the authenticated GitHub connector, but that connector does not provide a local executable checkout. Therefore the full suite is **not claimed as executed/passing** in this run.

No GitHub Actions workflow was added, triggered, or rerun merely to compensate, preserving the project's low-noise CI/storage policy.

No Grafana, Gemini, Google Cloud, or remediation credential was required for these changes.

### Decisions made

1. Activation binds both semantic telemetry configuration and datasource identity. Proving only the profile would still allow runtime to point at a different Grafana datasource after preflight.
2. The artifact stores the datasource SHA-256 rather than raw UID to reduce unnecessary operational metadata in audit/config handoffs.
3. Activation is deliberately time-bounded; passing telemetry once must not become permanent authorization to operate against a production whose telemetry topology may later drift.
4. Seven days is a hard upper TTL bound; production operators can choose a much shorter validity window.
5. The built-in default simulator profile is the only activation exception so local/free development remains frictionless. Real production mappings fail closed.
6. Activation hashes are drift pins, not signatures. Tamper resistance belongs to deployment/file-integrity controls and a later durable control-plane implementation.
7. Activation provenance hashes are copied into investigation audit events, linking incident evidence back to the exact preflighted configuration without exposing the datasource UID.

### Current blockers / unknowns

- Full deterministic Python suite has not executed in this automation environment because a local GitHub checkout remains unavailable.
- Full Compose startup and end-to-end official MCP Gate A remain unverified on a Docker-capable host.
- The eight-read preflight, activation artifact, six-read diagnosis, and two-read recovery loop have not yet been exercised through one live `grafana/mcp-grafana:1.1.0` process here.
- OIDC/IAP integration, Loki corroboration, Gemini explanation/orchestration, operator UI, durable multi-user/tamper-resistant audit storage, and Google Cloud deployment remain implementation gates.
- Runtime wiring still needs one production launcher/bootstrap path that loads the telemetry mapping and activation artifact, derives the datasource identity from the MCP client/config, and constructs the authenticated API service without hand-written Python glue.

## Single best next step

**Build a production runtime/bootstrap entrypoint that loads the strict telemetry profile + activation artifact, starts the official Grafana MCP metric client, verifies the activation against that client's datasource identity, wires `IncidentService` + authenticated HTTP API + audit sink, and refuses non-loopback operation unless a production authentication provider and fresh activation are both present. Add credential-free wiring tests so the complete startup safety policy is executable even without Grafana keys.**
