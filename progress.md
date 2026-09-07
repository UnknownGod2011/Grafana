# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable production path now covers:

`strict telemetry mapping → metric/Loki activation pins → official Grafana MCP evidence → deterministic diagnosis + Loki corroboration → authenticated IncidentService → optional revision-bound Gemini briefing → approval-gated remediation → telemetry recovery verification → bounded durable audit → authenticated operator cockpit/timeline → durable Cloud Logging timeline reconstruction → versioned incident lifecycle checkpoints with local atomic storage or signed/GCS persistence → bounded checkpoint conflict/health observability → Cloud Run/IAP deployment → independent liveness/readiness + bounded readiness cache/backoff/self-observability`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Production Prometheus and Loki datasource identities and semantic contracts are pinned by expiring activation artifacts.
- Gemini remains advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact deterministic evidence revision.
- A fresh investigation always clears prior approval/outcome state before persisting the new revision.
- Audit history and mutable lifecycle state are separate persistence concerns.
- Restored checkpoints must match the configured telemetry scope and recompute to the persisted evidence revision.
- Local checkpoints are atomic owner-only JSON and are never presented as Cloud Run durability.
- Production GCS checkpoints require both object-generation preconditions and HMAC-SHA-256 authenticity; bucket write permission alone is insufficient to forge an approved state.
- GCS generation conflicts fail closed and are observable separately from provider/storage failures.
- Checkpoint metrics contain only fixed labels and never bucket/object names, generations, incident IDs, revisions, credentials, provider exceptions, or signing material.
- Provider remediation metadata/details, credentials, Gemini output, Grafana secrets, and the checkpoint signing secret are not persisted in lifecycle checkpoints.
- Standard Cloud Run production remediation remains disabled.
- `/healthz` proves process liveness only; `/readyz` proves the bounded evidence plane; `/metrics` exposes fixed non-sensitive readiness and checkpoint telemetry.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP integration with datasource/Prometheus/Loki read tools and writes/proxied tools disabled.
- Deterministic incident investigation and bounded Loki corroboration.
- Strict configurable telemetry mapping, metric/Loki preflight, and expiring activation pins.
- Approval-gated remediation and Grafana telemetry-only recovery proof.
- Credential-isolated HTTPS production remediation transport with deterministic idempotency identity.
- Bounded revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity provider and bounded Cloud Logging audit sink.
- Dedicated non-root Cloud Run image with embedded official Grafana MCP binary and remediation disabled.
- `/healthz` liveness + fail-closed `/readyz` with cached/read-only MCP datasource reachability.
- Prometheus-format StageGuard readiness self-observability.
- Authenticated same-origin operator cockpit for evidence, Gemini briefing, typed revision approval, execution and recovery state.
- Bounded incident audit timeline with sequence pagination, actor pseudonymization, payload allow-lists, and durable Cloud Logging reconstruction.
- Versioned `stageguard.incident-checkpoint.v1` lifecycle persistence.
- Credential-free atomic JSON checkpoint store for local development.
- Optional Google Cloud Storage checkpoint store using ADC, fixed deployment-owned object mapping, optimistic generation preconditions, and HMAC-SHA-256 authenticity.
- Restart restoration of incident report/revision/approval/consumed outcome with fail-closed scope/revision validation.
- Bounded checkpoint conflict classification and Prometheus self-observability for checkpoint loads/saves/latency.

## Run log — 2026-09-07 — checkpoint conflict/health observability

### Inspected at start

Read `progress.md` completely before selecting work. Then inspected the repository surfaces directly relevant to the previous handoff:

- `runtime/incident_checkpoint.py`
- `runtime/readiness.py`
- `runtime/api.py`
- `runtime/incident_service.py`
- `runtime/bootstrap.py`
- `runtime/tests/test_gcs_checkpoint.py`
- `INCIDENT_CHECKPOINTS.md`

The previous handoff identified real multi-instance GCS acceptance as the next empirical gate. External credentials/resources are not available in this run, so the highest-value unblocked increment was to harden the exact observable failure semantics needed for that test: distinguish optimistic-concurrency conflicts from generic checkpoint failures, expose bounded metrics, and preserve fail-closed behavior.

### Exact changes made

Updated `runtime/incident_checkpoint.py`:

- introduced `CheckpointConflictError`, a bounded public concurrency-failure type;
- added `_http_status()` to classify provider failures by numeric HTTP status without copying provider exception text;
- GCS HTTP 412 generation-precondition failures now raise `CheckpointConflictError("incident checkpoint concurrent update conflict")`;
- all other GCS write failures remain bounded `RuntimeError("incident checkpoint write failed")`;
- added `ObservableCheckpointStore`, a thread-safe decorator for any checkpoint backend;
- records checkpoint load results as `ok`, `empty`, or `failed`;
- records checkpoint save results as `ok`, `conflict`, or `failed`;
- records only last load/save latency and a coarse latest-operation success gauge;
- re-raises every underlying exception unchanged by policy; no retry, merge, or overwrite is attempted;
- emitted Prometheus metrics use only fixed operation/result labels and contain no dynamic storage or incident identities.

Updated `runtime/bootstrap.py`:

- JSON and GCS checkpoint backends are now wrapped in `ObservableCheckpointStore` automatically;
- `none` remains no-store/no-metrics checkpoint mode;
- credential and signing-key handling is unchanged.

Updated `runtime/api.py`:

- `/metrics` now combines existing evidence-plane readiness metrics with checkpoint metrics when the configured store exports them;
- no new HTTP endpoint or caller-controlled metric labels were added;
- bumped server version to `StageGuard/0.8`;
- fallback text now says StageGuard metrics are unavailable rather than implying only readiness metrics exist.

Added `runtime/tests/test_checkpoint_observability.py`:

- verifies empty load and successful save counters;
- verifies bounded latency metrics;
- verifies concurrency conflict is counted separately from generic failure;
- verifies generic load/save failures are counted;
- verifies provider exception text, incident ID, and production ID do not appear in metrics.

Updated `runtime/tests/test_gcs_checkpoint.py`:

- added a fake HTTP-412 precondition failure;
- verifies a GCS generation race becomes `CheckpointConflictError`;
- verifies provider exception detail is not exposed by the bounded conflict exception.

Updated `INCIDENT_CHECKPOINTS.md`:

- documented the 412 conflict contract;
- documented all checkpoint metric names and bounded labels;
- documented privacy exclusions;
- explicitly states that conflicts remain fail-closed and are not blindly retried.

### Commits produced this run

- `6142d7cf` — add bounded checkpoint conflict observability
- `2569b448` — wire checkpoint observability into runtime
- `6b51f5ed` — expose bounded checkpoint metrics
- `8a3d1a23` — test checkpoint observability and conflict metrics
- `7f684e59` — test bounded GCS checkpoint conflict classification
- `acdfbff4` — document checkpoint conflict observability

### Tests / checks / results

No GitHub Actions workflow was created, triggered, or rerun.

The repository is accessible through the authenticated GitHub connector, but this automation environment still does not provide a normal local checkout from which the Python suite can be executed. Therefore the new tests are **not claimed as passing in this run**. No Grafana, Loki, Gemini, IAP, Cloud Logging, Cloud Storage, Secret Manager, operator, or remediation credential was used, and no production resource was changed.

### Decisions made

1. **Classify 412 conflicts separately.** A generation-precondition conflict means another writer won the optimistic-concurrency race; it is operationally different from storage unavailability.
2. **Remain fail-closed.** A conflict is re-raised. StageGuard does not retry an approval-bearing checkpoint without first reloading and revalidating current state.
3. **Observe through a decorator.** Checkpoint storage semantics remain separate from telemetry concerns, and local/GCS backends share the same bounded metrics contract.
4. **Keep labels fixed.** No bucket, object, generation, incident, revision, actor, production/feed, credential, exception, or provider string becomes a Prometheus label/value.
5. **Do not add checkpoint failure to `/readyz` yet.** Readiness currently proves the evidence plane. Treating one historical checkpoint conflict as permanent traffic ineligibility would be incorrect; a production health policy should be based on bounded recent failure state and must be designed after real multi-instance acceptance data.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because there is no runnable checkout path available here.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- The GCS adapter has fake-client coverage but has not yet been exercised against an actual private bucket/service account.
- A real deployment still needs secure injection of `STAGEGUARD_CHECKPOINT_HMAC_KEY`.
- Multi-instance Cloud Run behavior still needs empirical testing; StageGuard now has the bounded conflict telemetry needed to observe that test safely.
- The cockpit still needs a real Cloud Run + IAP browser acceptance.
- Grafana MCP readiness and full metric+Loki investigation still need acceptance against a real Grafana Cloud/self-hosted production instance.

## Single best next step

**Perform a private multi-instance GCS acceptance in a runnable environment: start two StageGuard instances against the same signed checkpoint object, create one exact-revision approval, deliberately race lifecycle writes, confirm one writer succeeds and the other produces `stageguard_checkpoint_saves_total{result="conflict"}`, then reload/revalidate the winning checkpoint before deciding whether a narrow compare-and-retry policy is safe for non-approval transitions. Do not add blind retries.**
