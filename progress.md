# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable vertical slice now includes a canonical fail-closed runtime/bootstrap path plus a governed, explicitly enabled production-remediation transport:

`versioned telemetry mapping → eight-read read-only preflight → hash-pinned/time-bounded activation artifact → production bootstrap → official Grafana MCP metric adapter → bounded six-read investigator → activation-enforced audited IncidentService → trusted operator identity → revision-bound approval → governed allowlisted remediation policy → explicit credential-isolated HTTPS transport → bounded two-read recovery verification`

Core invariants:

- Grafana is the read-only evidence plane; write credentials remain separate.
- Callers never provide raw PromQL, datasource IDs, remediation actions, targets, write endpoints, or credentials through the incident API.
- Existing production metric/label names are mapped through validated configuration, not interpolated as raw query fragments.
- Every production mapping explicitly defines all semantic bindings; omitted values never silently fall back to demo scope.
- Activation preflight performs exactly the six investigation reads and two recovery reads and requires one numeric sample for every slot.
- Successful preflight produces a time-bounded activation artifact binding the complete validated telemetry profile and datasource identity by SHA-256.
- Non-default production profiles cannot construct `IncidentService` without a matching, non-stale activation record; profile/datasource drift fails closed.
- The canonical bootstrap derives datasource identity from the actual MCP metric client configuration instead of accepting a second runtime datasource argument.
- Non-loopback HTTP startup requires a process-owned production-capable authentication provider.
- Production writes remain disabled unless `--enable-production-remediation` is supplied or a host explicitly injects a remediation factory.
- The production write endpoint and write bearer credential are process-owned and separate from the API/operator and Grafana evidence credentials.
- The production-remediation policy pins exactly one action, production, and uplink; deterministic evidence-bound operation IDs are reused for retries and re-approval of identical evidence.
- The concrete HTTPS transport propagates the operation ID as `Idempotency-Key`, strictly validates the server echo, bounds response size, and does not expose response bodies/endpoints/credentials in action metadata.
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
- Concrete HTTPS remediation transport with a separate process-owned credential, strict response contract, and server idempotency-key propagation.
- Explicit bootstrap production-write opt-in; safe disabled-remediation behavior remains the default.
- Loopback-only reference remediation receiver proving server-side idempotency semantics without mutating real infrastructure.

## Run log — 2026-09-07 — explicit production remediation transport

### Inspected at start

Read `progress.md` completely before deciding what to implement. Inspected the connected repository and current `main`, especially:

- `runtime/production_remediation.py`
- `runtime/remediation.py`
- `runtime/bootstrap.py`
- `runtime/tests/test_bootstrap.py`
- root `README.md`
- latest commits on `main`

The prior handoff's single best next step was still correct: StageGuard had a production-safe policy abstraction but no concrete deployment transport or canonical bootstrap opt-in for it.

### Exact changes made

Added `runtime/http_remediation_transport.py`:

- introduced the first concrete `HttpRemediationTransport` for credentialed production writes;
- requires an absolute HTTPS URL and rejects HTTP, URL-embedded credentials, query strings, and fragments;
- requires a process-owned bearer credential and rejects newline-bearing header values;
- sends only the immutable `RemediationRequest` fields owned by the governed policy layer;
- sends the deterministic operation identity as both JSON `operation_id` and HTTP `Idempotency-Key`;
- caps response bodies at 16 KiB;
- requires the success response schema to contain exactly `accepted` and `operation_id`;
- requires the server to echo the exact operation identity before StageGuard accepts the response;
- marks only bounded transient statuses (`408`, `425`, `429`, `500`, `502`, `503`, `504`) retryable;
- converts network failures into a narrow retryable transport result without copying endpoint, response body, or credential data into metadata.

Updated `runtime/bootstrap.py`:

- added explicit `--enable-production-remediation` startup opt-in;
- added process-owned remediation endpoint/token env names (`STAGEGUARD_REMEDIATION_ENDPOINT`, `STAGEGUARD_REMEDIATION_TOKEN` by default);
- wires `HttpRemediationTransport` into `AllowlistedProductionRemediationClient` only after explicit opt-in;
- keeps `DisabledRemediationClient` as the production default even if remediation environment variables happen to be present;
- rejects production-write opt-in for the deterministic demo profile;
- rejects simultaneous host `remediation_factory` injection and CLI production-remediation opt-in to avoid ambiguous write ownership;
- preserves datasource activation verification, network auth policy, and safe cleanup on startup failure.

Added `runtime/tests/test_http_remediation_transport.py` with credential-free coverage for:

1. HTTPS/credential URL validation;
2. deterministic idempotency header + immutable request payload propagation;
3. wrong operation echo and unknown response-field rejection;
4. bounded HTTP retry classification;
5. endpoint/credential redaction from transport results after network failure;
6. oversized/malformed success response failure behavior.

Extended `runtime/tests/test_bootstrap.py` with coverage for:

1. separate remediation settings required after explicit opt-in;
2. successful explicit wiring to `AllowlistedProductionRemediationClient`;
3. demo telemetry refusing the production-write opt-in.

Added `runtime/remediation_receiver.py`:

- loopback-only reference server for exercising the transport contract safely;
- bearer authentication with constant-time comparison;
- strict request schema and request-size bounds;
- mandatory equality between `Idempotency-Key` and JSON `operation_id`;
- idempotent acceptance of an exact repeated request;
- `409` refusal if the same operation identity is reused for a different mutation;
- in-memory operation storage only; no infrastructure mutation.

Added `runtime/tests/test_remediation_receiver.py` covering exact retry idempotency, operation-ID collision refusal, authentication, and header enforcement.

Updated root `README.md` to document:

- the explicit production-write startup path;
- separate operator/API and remediation write credentials;
- strict remediation receiver response contract;
- retry/response/redaction behavior;
- the local reference receiver;
- revised repository map and roadmap.

### Commits produced this run

- `ecf042d2` — credential-isolated HTTP remediation transport
- `50cf30fa` — HTTP transport safety-contract tests
- `50ac3214` — explicit production remediation bootstrap opt-in
- `8eec8c0c` — bootstrap opt-in regression tests
- `fdd03bd6` — production transport documentation
- `f2be6b63` — loopback reference remediation receiver
- `f0784c28` — receiver idempotency tests
- `e5ffeff9` — receiver documentation and roadmap update

### Tests / checks / results

The connected GitHub repository accepted all source, test, bootstrap, receiver, and documentation writes. The new files were structured to remain dependency-free and credential-free under the existing Python unittest model.

The automation environment still does not expose a runnable checked-out repository tree, so these deterministic commands were **not executed here and are not claimed as passing**:

```bash
python -m py_compile runtime/*.py runtime/tests/*.py
python -m unittest discover -s runtime/tests -v
```

No GitHub Actions workflow was created, triggered, or rerun as a substitute, preserving the low-noise CI/storage requirement. No Grafana, Google Cloud, Gemini, or production remediation credential was used.

### Decisions made

1. **Production writes require two independent gates.** Human approval remains necessary at incident time, and process startup must separately opt into production remediation.
2. **Credential presence does not enable writes.** The startup flag is mandatory; this protects against accidental secret injection into a diagnosis-only deployment.
3. **The remediation endpoint is deployment-owned, not incident-owned.** It comes only from process configuration and cannot be overridden by API callers or telemetry mapping.
4. **The receiver must echo the operation ID.** A `2xx` response alone is insufficient to establish that the server handled the intended idempotent operation.
5. **Unknown success payload fields fail closed.** This prevents silently accepting a response contract that drifted from StageGuard's audited semantics.
6. **Only transient failures are retryable.** Policy/auth/conflict/client failures do not get automatic retries.
7. **The reference receiver is deliberately loopback-only and non-mutating.** It proves the server contract without becoming an unsafe pseudo-production control plane.
8. **Transport acceptance is still not recovery.** Existing consecutive Grafana/Prometheus verification remains authoritative.

### Current blockers / unknowns

- Full deterministic Python suite has not executed in this automation environment because a runnable local checkout is unavailable.
- Full Compose startup and end-to-end official MCP Gate A remain unverified on a Docker-capable host.
- The eight-read preflight, activation artifact, bootstrap, six-read diagnosis, approval, concrete HTTPS write transport, and two-read recovery loop have not yet been exercised through one live `grafana/mcp-grafana:1.1.0` process here.
- The reference remediation receiver is contract-only; a real deployment endpoint/provider implementation is still environment-specific and intentionally absent.
- OIDC/IAP integration, Loki corroboration, Gemini explanation/orchestration, operator UI, durable multi-user/tamper-resistant audit storage, and Google Cloud deployment remain implementation gates.

## Single best next step

**Add Loki/log corroboration as a second read-only evidence plane behind a bounded semantic log-query adapter, record metric+log provenance in the incident report/audit trail, and keep diagnosis fail-closed when corroborating log evidence is unavailable or ambiguous. This is now higher value than adding more remediation mechanics because the production write boundary has an executable transport contract while evidence breadth is still metrics-only.**
