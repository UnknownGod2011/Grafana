# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable production path now covers:

`strict telemetry mapping → metric/Loki activation pins → official Grafana MCP evidence → deterministic diagnosis + Loki corroboration → authenticated IncidentService → optional revision-bound Gemini briefing → approval-gated remediation → telemetry recovery verification → bounded durable audit → authenticated operator cockpit/timeline → durable Cloud Logging timeline reconstruction → versioned incident lifecycle checkpoints with local atomic storage or signed/GCS persistence → Cloud Run/IAP deployment → independent liveness/readiness + bounded readiness cache/backoff/self-observability`

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
- Provider remediation metadata/details, credentials, Gemini output, Grafana secrets, and the checkpoint signing secret are not persisted in lifecycle checkpoints.
- Standard Cloud Run production remediation remains disabled.
- `/healthz` proves process liveness only; `/readyz` proves the bounded evidence plane; `/metrics` exposes fixed non-sensitive readiness telemetry.

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

## Run log — 2026-09-07 — restart-safe incident lifecycle checkpoints

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected the repository surfaces most relevant to the previous handoff:

- `runtime/incident_service.py`
- `runtime/remediation.py`
- `runtime/production_remediation.py`
- `runtime/investigator.py`
- `runtime/log_evidence.py`
- `runtime/bootstrap.py`
- `runtime/cloudrun_entrypoint.py`
- `runtime/requirements-cloudrun.txt`
- existing incident/bootstrap/Cloud Run tests
- `README.md`
- `.gitignore`

The highest-value gap was exactly the previous handoff: durable audit provenance survived a restart, but the current `IncidentSnapshot`, evidence revision, approval-consumption boundary and recovery state did not.

### Research / attribution checked

Verified current official Google Cloud Storage documentation before finalizing the production adapter. Google documents generation-match preconditions as the mechanism for avoiding races/data corruption: use `if_generation_match=0` for create-only writes and the current object generation for updates. The Python client documentation also confirms object generations change on each upload and can be used as conditional parameters.

References:

- https://docs.cloud.google.com/storage/docs/uploading-objects
- https://docs.cloud.google.com/python/docs/reference/storage/latest/generation_metageneration

### Exact changes made

Added `runtime/incident_checkpoint.py`:

- introduced `IncidentCheckpoint` and `CheckpointStore` abstraction;
- defined strict versioned `stageguard.incident-checkpoint.v1` canonical state;
- persists only incident ID, deterministic revision/report, matching approval, bounded consumed outcome and audit sequence;
- SHA-256 detects corruption of canonical state;
- production mode additionally signs canonical state with HMAC-SHA-256;
- production HMAC key must be at least 32 bytes and is never stored in the checkpoint;
- malformed, oversized, wrong-schema, wrong-digest, wrong-HMAC and unverifiable signed documents fail closed;
- provider remediation `detail` and arbitrary `metadata` are stripped from persisted state;
- restored action detail becomes the fixed string `restored checkpoint` and metadata becomes `{}`;
- `JsonCheckpointStore` uses owner-only mode, temporary-file write, `fsync`, and atomic `os.replace`;
- local checkpoint paths reject symlinks on read;
- `GoogleCloudStorageCheckpointStore` uses a fixed deployment-owned object name, lazy `google-cloud-storage` import, ADC, signed state, and object-generation preconditions;
- GCS create uses `if_generation_match=0`; updates reload the current generation and require that exact generation;
- traversal-like checkpoint object names are rejected.

Updated `runtime/incident_service.py`:

- accepts an optional checkpoint store;
- restores lifecycle state during service construction before serving requests;
- recomputes the deterministic report revision and rejects mismatch;
- rejects restored production/feed scope drift;
- reconstructs the policy-owned approval and rejects action/production/target drift;
- rejects outcomes with no approval;
- restores audit sequence and, when a durable audit reader is available, advances to the highest bounded durable sequence observed to avoid trivial sequence reuse after a checkpoint/audit timing gap;
- persists state after every lifecycle audit record so investigation, briefing sequence advancement, approval and remediation/recovery transitions update the checkpoint;
- a fresh investigation continues to construct a new snapshot with `approval=None, outcome=None`, so a previous approval cannot survive new evidence;
- a persisted outcome remains single-use after restart because `execute_approved()` refuses any snapshot with an existing outcome.

Updated `runtime/bootstrap.py`:

- added `none`, `json`, and `gcs` checkpoint backends;
- programmatic `build_runtime()` keeps checkpointing disabled by default to avoid changing existing test/caller state unexpectedly;
- CLI local development defaults to `.stageguard/incident-checkpoint.json`;
- GCS mode reads bucket name and signing secret from environment-owned settings rather than CLI values;
- production signing secret defaults to `STAGEGUARD_CHECKPOINT_HMAC_KEY` and never enters argv or browser state;
- added lazy GCS checkpoint construction alongside existing Cloud Logging/IAP/Gemini optional integrations.

Updated `runtime/cloudrun_entrypoint.py`:

- Cloud Run enables GCS lifecycle persistence only when `STAGEGUARD_CHECKPOINT_BUCKET` is configured;
- when a bucket is configured, startup also requires `STAGEGUARD_CHECKPOINT_HMAC_KEY` before bootstrap;
- without a bucket, Cloud Run explicitly passes `--checkpoint-backend none` rather than using ephemeral container storage and calling it durable;
- optional `STAGEGUARD_CHECKPOINT_OBJECT` remains deployment-owned;
- production remediation remains impossible to enable through this standard entrypoint.

Updated production dependencies:

- added `google-cloud-storage>=2.18,<4` to `runtime/requirements-cloudrun.txt`.

Added/hardened tests:

- `runtime/tests/test_incident_checkpoint.py` covers approval restoration, one-time post-restart execution, consumed approval after a second restart, fresh-investigation invalidation, tamper rejection, provider-metadata stripping, and versioned documents;
- `runtime/tests/test_gcs_checkpoint.py` covers create/update generation preconditions, wrong-HMAC failure, forged-state failure, short signing keys, and object-name bounds;
- `runtime/tests/test_cloudrun_entrypoint.py` now verifies no-checkpoint Cloud Run default, GCS opt-in, mandatory HMAC secret, secret non-disclosure in argv, and fixed safe production composition.

Documentation / repository hygiene:

- added `INCIDENT_CHECKPOINTS.md` with local/GCS deployment and trust-boundary guidance;
- updated `README.md` so the executable vertical slice, safety model, repository structure and roadmap include lifecycle checkpoints;
- `.stageguard/` is now ignored by Git so local lifecycle/audit/config state cannot be committed accidentally.

### Commits produced this run

- `c6212531` — add integrity-checked incident checkpoint store
- `6e3f8a21` — fix checkpoint digest verification
- `27440687` — restore and persist incident lifecycle checkpoints
- `33f05757` — harden checkpoint privacy and add durable GCS store
- `81ecaf1a` — add incident checkpoint restart safety tests
- `4fa124ea` — add optional Cloud Storage checkpoint dependency
- `19e8de82` — wire local and GCS lifecycle checkpoints into runtime
- `0e04bc00` — make Cloud Run checkpoint persistence explicit
- `f71b2575` — test explicit Cloud Run checkpoint mode
- `b2732985` — ignore local StageGuard runtime state
- `1db83eca` — add GCS checkpoint concurrency tests
- `3e2b7acd` — document restart-safe incident checkpoints
- `38c3491b` — document restart-safe incident lifecycle
- `c07c82bb` — require HMAC authenticity for production checkpoints
- `5377f1d0` — require checkpoint signing secret for GCS state
- `6a6f7e8b` — test signed GCS checkpoint authenticity
- `abe88c22` — fail closed without checkpoint HMAC secret
- `92565427` — test checkpoint HMAC startup boundary
- `ebe11d00` — document signed production checkpoint state

### Tests / checks / results

Attempted a clean checkout and targeted suite with:

`PYTHONPATH=runtime python -m unittest runtime.tests.test_incident_checkpoint runtime.tests.test_gcs_checkpoint runtime.tests.test_cloudrun_entrypoint -v`

The execution container again failed before Python started because DNS resolution for `github.com` is unavailable:

`fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com`

Therefore the new tests and `py_compile` are **not claimed as passing** in this runtime. No GitHub Actions workflow was created, triggered, or rerun as a workaround.

No Grafana, Loki, Gemini, IAP, Cloud Logging, Cloud Storage, Secret Manager, operator, or remediation credential was used. No production resource was changed.

### Decisions made

1. **Separate audit persistence from lifecycle persistence.** Audit history is an append-only provenance stream; restart state is a compact current-state checkpoint.
2. **Never trust a persisted revision string by itself.** Restoration recomputes the revision from the deterministic report before accepting approval state.
3. **Do not persist provider remediation metadata.** It is not required to enforce single-use approval and may contain infrastructure/provider details.
4. **Do not claim local disk as Cloud Run durability.** The production entrypoint selects no checkpoint unless a durable bucket is explicitly configured.
5. **Use GCS generation preconditions.** Competing writers fail rather than silently overwriting newer state, matching current Google guidance.
6. **Require checkpoint authenticity, not only corruption detection.** SHA-256 alone would let a bucket writer recompute a forged approved state; production GCS therefore requires HMAC-SHA-256 with a separate server-owned secret.
7. **Keep the HMAC key out of argv and persisted state.** It is read from environment-owned secret configuration only when GCS mode is selected.
8. **Preserve remediation idempotency across the remaining crash window.** A crash can still happen after the external action accepts but before checkpoint commit; the production remediation operation ID is deterministic for the same report/action so retry uses the same idempotency identity.
9. **Keep local/free development lightweight.** JSON checkpoints remain standard-library-only and unsigned because their trust boundary is owner-only local filesystem state, not a shared cloud authorization object.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted because the local execution environment cannot resolve `github.com` for a runnable checkout.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- The new GCS adapter has fake-client coverage but has not yet been exercised against an actual private bucket/service account.
- A real deployment still needs a secure injection mechanism for `STAGEGUARD_CHECKPOINT_HMAC_KEY` (for example Cloud Run secret-backed environment configuration); no secret was created or modified in this run.
- Multi-instance Cloud Run behavior has not yet been empirically exercised. Generation preconditions prevent silent checkpoint overwrite, and deterministic remediation operation IDs protect the external mutation retry boundary, but real concurrent operator traffic still needs acceptance testing.
- The cockpit has not yet been exercised through a real Cloud Run + IAP browser session.
- Grafana MCP readiness and full metric+Loki investigation have not yet been exercised against a real Grafana Cloud/self-hosted production instance in this environment.

## Single best next step

**Run the checkpoint path in a real executable environment and harden from evidence: first execute the new local crash/restart tests plus full `py_compile`/unittest discovery; then perform one private-GCS acceptance using a least-privilege service account and secret-backed `STAGEGUARD_CHECKPOINT_HMAC_KEY`, including two concurrent service instances racing to update the same approval checkpoint, and use the observed failure semantics to add explicit checkpoint health/conflict telemetry and any required retry policy without weakening fail-closed approval behavior.**
