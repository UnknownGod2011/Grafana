# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable vertical slice now includes a canonical fail-closed runtime/bootstrap path around the previously implemented activation-enforced lifecycle:

`versioned telemetry mapping → eight-read read-only preflight → hash-pinned/time-bounded activation artifact → production bootstrap → official Grafana MCP metric adapter → bounded six-read investigator → activation-enforced audited IncidentService → trusted operator identity → revision-bound approval → separate remediation boundary → bounded two-read recovery verification`

Core invariants:

- Grafana is the read-only evidence plane; write credentials remain separate.
- Callers never provide raw PromQL, datasource IDs, remediation actions, or targets through the incident API or telemetry mapping file.
- Existing production metric/label names are mapped through validated configuration, not interpolated as raw query fragments.
- Every production mapping explicitly defines all semantic bindings; omitted values never silently fall back to demo scope.
- Activation preflight performs exactly the six investigation reads and two recovery reads and requires one numeric sample for every slot.
- Successful preflight produces a time-bounded activation artifact binding the complete validated telemetry profile and datasource identity by SHA-256.
- Non-default production profiles cannot construct `IncidentService` without a matching, non-stale activation record; profile/datasource drift fails closed.
- The canonical bootstrap derives datasource identity from the actual MCP metric client configuration instead of accepting a second runtime datasource argument.
- Non-loopback HTTP startup requires a process-owned production-capable authentication provider.
- Production bootstrap does not silently enable write capability: absent an explicit write adapter it uses a disabled remediation client.
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
- Canonical production bootstrap wiring mapping + activation + MCP datasource identity + audit + auth + service + HTTP bind policy.

## Run log — 2026-09-07 — canonical production runtime/bootstrap

### Inspected at start

Read `progress.md` completely before deciding what to implement. Inspected the current repository through the connected GitHub integration, especially:

- `runtime/incident_service.py`
- `runtime/api.py`
- `runtime/identity.py`
- `runtime/mcp_metric_client.py`
- `runtime/remediation.py`
- `runtime/activation.py`
- `runtime/onboarding.py`
- `runtime/telemetry.example.json`
- root `README.md`

The previous handoff identified the highest-value unblocked gap correctly: all runtime safety pieces existed, but starting StageGuard still required hand-written Python glue and therefore left room for production deployments to accidentally wire the wrong datasource, omit activation, expose loopback identity externally, or enable writes inconsistently.

### Exact changes made

Added `runtime/bootstrap.py`:

- added one canonical `build_runtime(...)` composition path;
- loads the strict versioned telemetry profile from disk;
- requires an activation artifact for every non-default production profile;
- constructs the official `McpPrometheusMetricClient` and passes **that client's actual `datasource_uid`** into `IncidentService` activation verification;
- loads the append-only `JsonlAuditLog`;
- chooses loopback-only fixed development identity only when binding to loopback and no bearer token is configured;
- requires `STAGEGUARD_API_TOKEN` (or an explicitly named token env var) for non-loopback binds;
- obtains the audit/operator subject from a process-owned env var rather than request JSON;
- returns a `RuntimeBundle` that owns the service, metric client, identity provider, and already-bound HTTP server;
- constructs the HTTP listener exactly once, eliminating a validate-then-rebind race in the first implementation draft;
- closes the MCP subprocess/transport and listening socket through one `RuntimeBundle.close()` path;
- adds CLI arguments for telemetry config, activation artifact, audit log, host, port, and the **names** of secret/subject environment variables without accepting secret values as CLI arguments.

Added `DisabledRemediationClient` as the production-safe default:

- non-demo production bootstrap does not silently obtain write capability;
- diagnosis, evidence review, approval, and audit can run while `/v1/execute` receives an action rejection until a host application deliberately injects an explicit remediation adapter;
- the deterministic demo profile continues using the existing loopback-only `SimulatorRemediationClient`.

Added `runtime/tests/test_bootstrap.py` with five credential-free startup-policy tests:

1. non-default production profile refuses startup without activation;
2. activation is checked against the datasource identity of the actual metric client instance, catching datasource drift;
3. non-loopback bind refuses startup without a process-owned bearer token;
4. loopback startup defaults to the local development identity and creates the audit sink;
5. an activated production runtime can start with bearer auth while retaining the disabled write boundary by default.

Updated root `README.md`:

- inserted bootstrap into the executable architecture and safety table;
- documented the canonical production startup command;
- documented bearer token/subject env handling;
- documented runtime verification against the actual MCP datasource identity;
- documented the safe disabled production remediation default;
- updated repository map, status, and roadmap.

### Tests / checks / results

After repository writes, attempted a clean checkout followed by:

```bash
python -m py_compile runtime/*.py runtime/tests/*.py
python -m unittest discover -s runtime/tests -v
```

The checkout failed before Python execution because the execution container still cannot resolve `github.com` (`Could not resolve host: github.com`). Therefore neither syntax compilation nor the unittest suite is claimed as executed/passing in this run.

The newly written `runtime/bootstrap.py` was fetched back through the authenticated GitHub connector and manually re-inspected after commit, including the final one-bind `RuntimeBundle` lifecycle.

No GitHub Actions workflow was added, triggered, or rerun merely to compensate, preserving the project's low-noise CI/storage policy. No Grafana, Gemini, Google Cloud, or remediation credential was required for the implementation.

### Decisions made

1. **Datasource identity has one source of truth at runtime.** Bootstrap takes it from `McpPrometheusMetricClient.datasource_uid`; callers do not independently pass a second datasource identity into the launcher.
2. **No non-loopback implicit identity.** External binds require a process-owned bearer credential. Loopback retains the frictionless deterministic development identity.
3. **Secrets are environment-owned, not CLI-owned.** The CLI accepts env-var names but not bearer secret values, reducing accidental shell-history/process-list exposure.
4. **Production writes are disabled by default.** An activated production can diagnose and collect approvals without acquiring mutation capability. A real write adapter must be injected deliberately with its own credentials/policy.
5. **The server socket is created once.** The first draft constructed and closed a server merely to validate bind/auth policy, then rebound it in `main`; that was replaced with a bundle that owns the already-bound server, avoiding a TOCTOU/race window.
6. **Activation remains the runtime admission gate.** Bootstrap does not duplicate activation semantics; it composes the existing `IncidentService` verifier so the safety rule stays centralized.

### Current blockers / unknowns

- Full deterministic Python suite has not executed in this automation environment because direct `github.com` DNS resolution remains unavailable to the local execution container.
- Full Compose startup and end-to-end official MCP Gate A remain unverified on a Docker-capable host.
- The eight-read preflight, activation artifact, new bootstrap, six-read diagnosis, approval, and two-read recovery loop have not yet been exercised through one live `grafana/mcp-grafana:1.1.0` process here.
- The production bootstrap intentionally has no write-capable remediation implementation yet; only the local simulator adapter can mutate state.
- OIDC/IAP integration, Loki corroboration, Gemini explanation/orchestration, operator UI, durable multi-user/tamper-resistant audit storage, and Google Cloud deployment remain implementation gates.

## Single best next step

**Implement a narrow allowlisted production remediation adapter with separate credentials, explicit idempotency keys, bounded timeout/retry behavior, immutable request/result audit metadata, and no caller-selectable URL/action/target. Add credential-free adapter tests and integrate it into bootstrap only behind explicit configuration, preserving `DisabledRemediationClient` as the default.**
