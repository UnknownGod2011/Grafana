# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable vertical slice now includes a canonical fail-closed runtime/bootstrap path plus a governed production-remediation policy boundary:

`versioned telemetry mapping → eight-read read-only preflight → hash-pinned/time-bounded activation artifact → production bootstrap → official Grafana MCP metric adapter → bounded six-read investigator → activation-enforced audited IncidentService → trusted operator identity → revision-bound approval → governed allowlisted remediation policy → deployment-owned write transport → bounded two-read recovery verification`

Core invariants:

- Grafana is the read-only evidence plane; write credentials remain separate.
- Callers never provide raw PromQL, datasource IDs, remediation actions, targets, or write endpoints through the incident API or telemetry mapping file.
- Existing production metric/label names are mapped through validated configuration, not interpolated as raw query fragments.
- Every production mapping explicitly defines all semantic bindings; omitted values never silently fall back to demo scope.
- Activation preflight performs exactly the six investigation reads and two recovery reads and requires one numeric sample for every slot.
- Successful preflight produces a time-bounded activation artifact binding the complete validated telemetry profile and datasource identity by SHA-256.
- Non-default production profiles cannot construct `IncidentService` without a matching, non-stale activation record; profile/datasource drift fails closed.
- The canonical bootstrap derives datasource identity from the actual MCP metric client configuration instead of accepting a second runtime datasource argument.
- Non-loopback HTTP startup requires a process-owned production-capable authentication provider.
- Production bootstrap does not silently enable write capability: absent an explicit write adapter it uses a disabled remediation client.
- The production-remediation policy pins exactly one action, production, and uplink, uses deterministic evidence-bound operation IDs, bounds retries/timeouts, and delegates credentialed I/O to a deployment-owned transport.
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
- Governed production-remediation policy with allowlisted action/target, deterministic operation identity, bounded retry/timeout policy, injected transport, and audited non-secret result metadata.

## Run log — 2026-09-07 — governed production remediation boundary

### Inspected at start

Read `progress.md` completely before deciding what to implement. Inspected the current repository through the connected GitHub integration, especially:

- `runtime/remediation.py`
- `runtime/incident_service.py`
- `runtime/bootstrap.py`
- `runtime/tests/test_remediation.py`
- root `README.md`

The previous handoff identified the highest-value unblocked gap correctly: production bootstrap was fail-closed but the only write-capable implementation was the loopback simulator. A production-safe policy layer for a real remediation integration did not yet exist.

### Exact changes made

Added `runtime/production_remediation.py`:

- introduced immutable `RemediationRequest` and `TransportResult` contracts;
- introduced a narrow `RemediationTransport` protocol so deployment code owns the actual credentialed endpoint while StageGuard owns remediation policy;
- added `AllowlistedProductionRemediationClient` that pins exactly one production ID and one uplink;
- hardcodes the only supported semantic action to `recover_uplink`;
- rejects target drift before any transport call;
- requires an evidence-bound StageGuard operation identity before production execution;
- limits per-attempt timeout to at most 10 seconds;
- permits at most three attempts;
- bounds retry delay to at most two seconds;
- retries only when the deployment transport marks failure as retryable (or a bounded timeout/OS transport failure occurs);
- reuses the exact immutable request and operation ID on every retry;
- returns only non-secret immutable metadata: adapter name, operation ID, attempt count, and transport status.

Updated `runtime/remediation.py`:

- added deterministic `remediation_operation_id(...)` derived from the complete diagnosed report plus fixed action/production/target;
- deliberately excludes the approving human identity from that key so re-approval of identical evidence does not produce a second infrastructure mutation after an uncertain retry;
- dispatches to `recover_uplink_idempotent(...)` when a client supports the governed production interface;
- retains the existing two-argument `recover_uplink(...)` compatibility path for the deterministic simulator and existing simple test doubles;
- extended `ActionResult` with optional metadata while preserving existing positional construction.

Updated `runtime/incident_service.py`:

- remediation completion audit events now persist the governed adapter's non-secret action metadata when available;
- bearer/write credentials, endpoint URLs, and arbitrary transport payloads are not added to audit events.

Added `runtime/tests/test_production_remediation.py` with credential-free coverage for:

1. deterministic operation identity and actor-independent re-approval behavior;
2. rejection of non-allowlisted targets before transport execution;
3. retry reuse of the exact immutable request/operation ID;
4. successful remediation still requiring Grafana telemetry recovery proof;
5. non-retryable failure stopping immediately without recovery reads;
6. timeout handling with bounded retries and timeout propagation;
7. rejection of unbounded timeout/retry configurations.

Updated root `README.md`:

- documented the governed production-remediation boundary;
- clarified that the deployment transport, not the incident caller, owns endpoint and write credentials;
- documented deterministic operation identity, retry/timeout bounds, audit metadata, and telemetry-only recovery proof;
- kept canonical bootstrap writes disabled by default;
- updated repository map, safety model, project status, and roadmap.

### Tests / checks / results

The repository connector accepted all final source/test/documentation writes. `runtime/production_remediation.py` was fetched back after commit and manually re-inspected for the final immutable request, allowlist, timeout/retry, and metadata behavior.

The local execution environment still does not provide a runnable checkout of the repository, so the deterministic Python commands below were not executed here and are **not** claimed as passing:

```bash
python -m py_compile runtime/*.py runtime/tests/*.py
python -m unittest discover -s runtime/tests -v
```

No GitHub Actions workflow was added, triggered, or rerun as a substitute, preserving the project's low-noise CI/storage policy. No Grafana, Gemini, Google Cloud, or remediation credential was required for this implementation.

One initial attempt to place credentialed HTTP transport logic directly inside the repository write was rejected by the repository safety layer. Rather than weakening policy or retrying around that control, the implementation was redesigned so StageGuard owns a provider-neutral, credential-free policy adapter and the deployment injects a narrow credentialed transport. This is also a cleaner separation of duties for the project.

### Decisions made

1. **Idempotency is bound to evidence, not the human actor.** The same diagnosed evidence + action + target yields the same operation identity even if a second operator re-approves it.
2. **Production policy and credentialed transport are separate modules.** StageGuard does not need to know arbitrary URLs or provider credential formats to enforce action/target/retry policy.
3. **No caller-selectable action or target.** The adapter constructs `recover_uplink` internally and accepts only the preconfigured production/uplink pair.
4. **Retries are safe only with the same operation identity.** Every retry receives the exact same immutable `RemediationRequest`.
5. **Transport acceptance is not recovery.** Existing two-read consecutive telemetry verification remains authoritative.
6. **Audit metadata is intentionally narrow.** Operation identity, adapter type, attempt count, and transport status are useful provenance; secrets and endpoint details are excluded.
7. **Bootstrap remains safe by default.** Existing `remediation_factory` injection is the explicit host hook; canonical CLI startup still uses `DisabledRemediationClient` for production.

### Current blockers / unknowns

- Full deterministic Python suite has not executed in this automation environment because a runnable local checkout is unavailable.
- Full Compose startup and end-to-end official MCP Gate A remain unverified on a Docker-capable host.
- The eight-read preflight, activation artifact, bootstrap, six-read diagnosis, approval, governed production action, and two-read recovery loop have not yet been exercised through one live `grafana/mcp-grafana:1.1.0` process here.
- A concrete deployment-specific `RemediationTransport` is intentionally not implemented yet; it needs a chosen provider/endpoint contract and separate write credential.
- OIDC/IAP integration, Loki corroboration, Gemini explanation/orchestration, operator UI, durable multi-user/tamper-resistant audit storage, and Google Cloud deployment remain implementation gates.

## Single best next step

**Add the first concrete deployment transport for `AllowlistedProductionRemediationClient` using a fixed provider-controlled endpoint and separate process-owned write credential, with server-side idempotency-key expectations, strict response parsing, credential-redaction tests, and explicit bootstrap opt-in. Preserve `DisabledRemediationClient` as the default and keep the provider-neutral policy layer unchanged.**
