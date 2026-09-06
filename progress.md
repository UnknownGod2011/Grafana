# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable vertical slice now includes configurable, validated telemetry bindings while preserving a fixed safety policy:

`telemetry profile → Prometheus/Grafana → official Grafana MCP → bounded six-read investigator → audited IncidentService → trusted operator identity → revision-bound approval → separate remediation adapter → bounded two-read recovery verification`

Core invariants:

- Grafana is the read-only evidence plane; write credentials remain separate.
- Callers never provide raw PromQL, datasource IDs, remediation actions, or targets through the incident API.
- Existing production metric/label names are mapped through validated configuration, not interpolated as raw query fragments.
- Missing evidence causes abstention.
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

## Run log — 2026-09-06 — configurable telemetry mappings

### Inspected at start

Read `progress.md` completely before deciding what to implement. Inspected the current repository and the safety-critical runtime files, especially:

- `runtime/investigator.py`
- `runtime/remediation.py`
- `runtime/incident_service.py`
- `runtime/tests/test_investigator.py`

The prior handoff identified hard-coded demo metric and label names as the highest-value portability gap. That remained correct: the policy was bounded, but a real production would have had to rename telemetry to match the demo schema.

### Exact changes made

Added `runtime/telemetry.py`:

- introduced immutable `TelemetryProfile` for production/feed/uplink identities, peer feeds, metric names, and label-key mappings;
- validates Prometheus metric identifiers and label identifiers with restrictive grammars;
- rejects empty required scope/peer bindings;
- escapes PromQL string-literal values including quotes, backslashes, and newlines;
- regex-escapes peer-feed values before constructing the bounded healthy-peer matcher;
- added `investigation_queries(profile)` which always emits the same six semantic evidence slots;
- added `recovery_queries(profile)` which always emits the same two recovery checks;
- retained `DEFAULT_TELEMETRY_PROFILE` matching the deterministic simulator, preserving existing callers and tests.

Updated `runtime/investigator.py`:

- `investigate()` now accepts a validated `TelemetryProfile` rather than relying on hard-coded query text;
- query count and semantic evidence classes remain exactly six;
- report scope and hypothesis now reflect the configured production/feed/uplink;
- missing mapped telemetry keeps the same fail-closed abstention semantics;
- compatibility constants and default `QUERIES` remain for existing tests/adapters.

Updated `runtime/remediation.py`:

- approval targets are derived from the same `TelemetryProfile` used for diagnosis;
- approval validation now verifies report production/feed/hypothesis against that profile;
- post-action recovery uses the same mapped metric/label names through exactly two queries;
- custom mappings therefore cannot diagnose one uplink and accidentally remediate/verify the demo uplink;
- the simulator actuator remains intentionally bound to the default local fixture only.

Updated `runtime/incident_service.py`:

- accepts one validated `telemetry_profile` at construction;
- propagates that exact profile through investigate → approve → execute/verify;
- no profile/query fields were added to the HTTP request surface.

Added `runtime/tests/test_telemetry.py` with seven deterministic tests covering:

1. custom production/metric/label mapping while retaining exactly six investigation reads;
2. production-scope quote escaping without turning values into arbitrary matchers;
3. peer-feed regex escaping;
4. rejection of unsafe metric identifiers;
5. rejection of unsafe label identifiers;
6. exactly two recovery query slots;
7. unchanged abstention when a mapped evidence source is missing.

### Tests / checks / results

This automation environment still cannot obtain a local checkout from GitHub, so the new Python suite was not executed here. I did not add or trigger GitHub Actions merely to compensate, avoiding noisy CI/storage usage.

The next executable host should run:

```bash
python -m py_compile runtime/*.py runtime/tests/*.py
python -m unittest discover -s runtime/tests -v
```

No live Grafana/MCP credential was required for this implementation; all new mapping tests are credential-free.

### Decisions made

1. Configuration maps semantic telemetry slots; it does not grant arbitrary PromQL capability.
2. Identifier-like configuration and label values are treated differently: identifiers are allowlisted by grammar, values are escaped as PromQL literals.
3. One immutable profile follows the whole incident lifecycle so diagnosis, approval target, remediation, and recovery cannot drift to different production scopes.
4. The fixed evidence budget is a policy invariant independent of metric naming.
5. Simulator write behavior remains fixture-specific; real production remediation must provide a separate adapter whose allowed targets are configured independently and explicitly.

### Current blockers / unknowns

- Full Compose startup and end-to-end official MCP Gate A remain unverified on a Docker-capable host.
- The six-query diagnosis and two-query recovery loop have not yet been exercised through a live `grafana/mcp-grafana:1.1.0` process in this environment.
- New mapping tests have not executed in this environment due lack of a local checkout.
- No persisted/onboarding configuration loader yet turns a user-owned mapping file into `TelemetryProfile` with preflight checks.
- OIDC/IAP integration, Loki corroboration, Gemini explanation/orchestration, operator UI, durable multi-user audit storage, and Google Cloud deployment remain implementation gates.

## Single best next step

**Build a safe production onboarding/preflight layer for `TelemetryProfile`: load a versioned local JSON configuration, reject unknown fields, validate the profile, execute the eight bounded queries read-only through the metric client, report exactly which semantic evidence slots are missing/ambiguous, and refuse activation until production scoping and required telemetry are proven. This turns the new mapping primitive into a real-user connection workflow without exposing generic PromQL or requiring credentials to be committed.**
