# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, explicit stale-telemetry detection, a credential-free metrics-outage rehearsal path, reproducibly pinned Grafana/Prometheus acceptance images, live runtime-version attestation, fail-closed Prometheus safety-query parsing, and a live query-local cardinality ambiguity probe.

Core invariants remain unchanged:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- A healthy watchdog value is trustworthy only while the observability path is delivering fresh samples.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, or non-finite Prometheus safety evidence must never be interpreted as a healthy acceptance signal.

## Run log — 2026-09-11 — live Prometheus cardinality ambiguity probe

### Inspected at start

Read `progress.md` completely before making changes. Inspected the repository tree and the current observability acceptance path, including:
- `runtime/watchdog_observability_acceptance.py`
- `runtime/watchdog_metrics_fixture.py`
- `runtime/tests/test_watchdog_observability_acceptance.py`
- `docker-compose.yml`
- `docs/runtime-metrics-ingestion.md`

Confirmed the previous strict parser rejects multi-series instant vectors, but the complete acceptance rehearsal did not yet prove that behavior through a real Prometheus query. The recorded next step proposed injecting a duplicate watchdog series. Reviewing Prometheus staleness behavior showed a reproducibility problem with persistent fixture-level duplicates: after switching back to one series, the removed series may remain queryable until Prometheus marks it stale, which can contaminate subsequent lifecycle checks or immediate reruns.

### Research / attribution

Reviewed current official Prometheus documentation before choosing the negative-probe design:
- `label_replace()` can add/replace a label on each instant-vector series.
- the `or` logical/set operator returns the union of vector elements when their complete label sets do not match.

These semantics let the rehearsal manufacture two label-distinct results from the single healthy watchdog series entirely at query time, without writing new samples.

Official references:
- https://prometheus.io/docs/prometheus/latest/querying/functions/#label_replace
- https://prometheus.io/docs/prometheus/latest/querying/operators/
- https://prometheus.io/docs/prometheus/latest/querying/api/

### Exact changes made

#### Added live query-local ambiguity proof

Updated `runtime/watchdog_observability_acceptance.py` with `AMBIGUITY_PROBE_QUERY`:

```promql
label_replace(stageguard_remediation_execution_deadline_exceeded, "stageguard_acceptance_probe", "left", "", "")
or
label_replace(stageguard_remediation_execution_deadline_exceeded, "stageguard_acceptance_probe", "right", "", "")
```

After StageGuard establishes a healthy `deadline_exceeded=0` sample, the rehearsal sends this expression through the same live Prometheus HTTP query path used by the safety checks. The expression returns two label-distinct copies of the source series. `prometheus_ambiguity_probe_rejected()` requires the existing strict parser to reject that response specifically with `Prometheus safety query must return exactly one series`.

The rehearsal fails if:
- Prometheus unexpectedly returns an accepted scalar-like result;
- StageGuard no longer rejects the multi-series vector;
- an unrelated parser failure is mistaken for successful ambiguity rejection;
- the live query cannot be executed or decoded.

The probe runs before the real deadline and stale-telemetry lifecycles. Because it creates labels only in the query result, it leaves no additional stored time series behind and does not make immediate reruns depend on Prometheus stale-marker timing.

The final PASS message now explicitly includes successful rejection of ambiguous Prometheus safety evidence.

#### Added focused regression coverage

Added `runtime/tests/test_watchdog_ambiguity_probe.py` covering:
- the probe expression references the watchdog metric twice;
- exactly two `label_replace()` branches are present;
- the branches use distinct `left`/`right` synthetic label values and `or` union semantics;
- the helper returns success only for the exact multi-series rejection;
- a mistakenly accepted `0.0` returns failure;
- an unrelated parser failure such as non-finite evidence does not count as a successful ambiguity proof.

Existing strict parser tests remain in `runtime/tests/test_watchdog_observability_acceptance.py` and continue to cover direct contradictory multi-series payloads, malformed response shapes, and NaN/Inf rejection.

#### Added rationale documentation

Added `docs/prometheus-acceptance-safety.md` explaining:
- why watchdog cardinality ambiguity is a safety-evidence integrity failure;
- the exact query-local PromQL probe;
- why query-local duplication was preferred over persistent duplicate fixture exposition;
- the relevant official Prometheus operator/function/API references;
- the boundary between this acceptance guard and normal production telemetry-label hygiene.

### Commits this run

- `a7a3fcfaddaa527fc87ae41b9fa403e9f972a0b6` — prove Prometheus cardinality ambiguity fails closed
- `9837ff7eba4416c60b6868c2c05b12df56bf73ce` — test live Prometheus ambiguity probe contract
- `9c7456a8711ab454a08b2316237c61737b8fcd1b` — document Prometheus acceptance ambiguity guard
- `9fb6e677ef0cee35a63129647d7fd01249bc4eeb` — record implementation handoff before final validation attempt

### Tests / checks / results

- Re-fetched the committed acceptance script through the GitHub API and verified the new constant, helper, pre-lifecycle ambiguity check, failure paths, and PASS message are present on `main`.
- Re-fetched `runtime/tests/test_watchdog_ambiguity_probe.py` and verified the focused regression coverage is committed to the intended repository.
- Compared the probe design against official Prometheus documentation: `label_replace()` preserves the source series while adding the synthetic label, and `or` unions label-distinct instant-vector elements, which is the required cardinality behavior.
- Attempted the focused test command from a fresh checkout:
  `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard-grafana && python -m unittest runtime.tests.test_watchdog_ambiguity_probe runtime.tests.test_watchdog_observability_acceptance`
- The environment failed before checkout with `Could not resolve host: github.com`; therefore the exact committed tests did not execute and no green claim is made.
- The full Docker observability rehearsal was not executed here for the same checkout/network limitation; it still requires a runnable Docker checkout with the pinned images.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Use a query-local adversarial cardinality probe rather than a fixture mode that emits persistent duplicate series. This exercises the real Prometheus HTTP path while avoiding stale-series residue between test phases/reruns.
2. Count only the parser's explicit multi-series rejection as a successful negative test. Other parse/API failures must not make the rehearsal look healthy.
3. Run the ambiguity probe only after a real healthy watchdog sample exists, so the synthetic branches are derived from actual scraped evidence rather than an empty vector.
4. Preserve the existing deadline and telemetry-outage lifecycles unchanged after the negative probe; the adversarial check is an additional gate, not a replacement.
5. Keep the test dependency-free and local; it adds no credentials, destinations, external writes, or CI load.

### Blockers / unknowns

- The new focused unit test and existing acceptance tests still need execution from a runnable checkout.
- The full Docker watchdog rehearsal still needs to run against the pinned Prometheus 3.13.3 and Grafana 13.2.1 images. It must attest live versions, prove the query-local ambiguity rejection, then prove deadline firing/resolution and stale-telemetry firing/resolution.
- Container digests are still not committed because an authoritative registry digest has not been verified through the available execution path.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity.
- Cloud Storage Policy Troubleshooter and live Gemini/Vertex acceptance still require authorized disposable-project credentials.

## Single best next step

**Run the complete credential-free Docker observability rehearsal in the first environment with Docker access and a runnable checkout. It must attest Prometheus 3.13.3 and Grafana 13.2.1, prove the new live ambiguity probe is rejected without contaminating subsequent queries, then prove both the remediation-deadline and stale-telemetry firing-and-resolution lifecycles. If that passes, capture the exact command/output as the new observability acceptance baseline.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the new watchdog freshness acceptance path, explicit image pins, live runtime-version attestation, strict Prometheus safety-query parsing, and the live ambiguity probe.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
