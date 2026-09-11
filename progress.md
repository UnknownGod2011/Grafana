# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, explicit stale-telemetry detection, a credential-free metrics-outage rehearsal path, reproducibly pinned Grafana/Prometheus acceptance images, live runtime-version attestation, and fail-closed Prometheus safety-query parsing in the observability rehearsal.

Core invariants remain unchanged:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- A healthy watchdog value is trustworthy only while the observability path is delivering fresh samples.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, or non-finite Prometheus safety evidence must never be interpreted as a healthy acceptance signal.

## Run log — 2026-09-11 — strict Prometheus acceptance evidence

### Inspected at start

Read `progress.md` completely before making changes. Inspected repository metadata plus:
- `runtime/watchdog_observability_acceptance.py`
- `runtime/tests/test_watchdog_observability_acceptance.py`
- `docker-compose.yml`

Confirmed the previously recorded runtime-version attestation is present and the Compose stack remains pinned to Prometheus 3.13.3 and Grafana 13.2.1.

While reviewing the acceptance boundary, identified a safety/reproducibility defect in `prometheus_query_value()`: it accepted the first result from any non-empty result list and directly converted its sample with `float()`. Prometheus instant-vector ordering is not guaranteed, and Prometheus represents special float values such as NaN/Inf as quoted sample strings. A duplicated/unexpectedly labeled metric could therefore return contradictory series and the rehearsal could accept whichever happened to be first; a non-finite sample could also flow into acceptance comparisons without a structural failure.

### Research / attribution

Checked the current official Prometheus HTTP API documentation before changing the parser. The API documents:
- instant-query `data.resultType` and `data.result` structure;
- instant vectors as per-series objects containing a two-element `value` pair;
- vector result ordering is not guaranteed unless explicitly sorted;
- special float values such as `NaN`, `Inf`, and `-Inf` are transported as quoted strings.

Official reference: https://prometheus.io/docs/prometheus/latest/querying/api/

### Exact changes made

#### Fail closed on ambiguous Prometheus safety evidence

Updated `runtime/watchdog_observability_acceptance.py` with `prometheus_query_value_from_payload()` and routed all watchdog/freshness instant queries through it.

The parser now requires:
1. a JSON object with `status == "success"`;
2. object-valued `data`;
3. `resultType == "vector"`;
4. list-valued `result`;
5. either an empty vector (represented as `None`, allowing polling to continue) or exactly one returned series;
6. an object-valued series;
7. exactly a two-element `value` pair;
8. a numeric-convertible sample that is finite.

It rejects multiple result series instead of choosing one arbitrarily. This is intentional: StageGuard's acceptance expressions are scalar-like safety signals and are expected to collapse to at most one sample. More than one sample means telemetry cardinality/configuration has drifted and acceptance must fail closed rather than guess which series is authoritative.

It also rejects NaN and positive/negative infinity. This prevents invalid numeric evidence from silently participating in equality or freshness comparisons.

#### Added regression coverage

Expanded `runtime/tests/test_watchdog_observability_acceptance.py` to cover:
- one valid finite instant-vector sample;
- an empty vector returning `None` for polling;
- contradictory duplicate/multi-series results failing closed;
- `NaN`, `Inf`, `+Inf`, and `-Inf` samples failing closed;
- failed Prometheus responses;
- missing/malformed `data`;
- non-vector result types;
- non-list result values;
- malformed series entries;
- malformed sample tuples;
- nonnumeric sample strings.

Existing runtime-version, alert identity, stale-query, telemetry-mode, timeout, and loopback-origin checks remain intact.

### Commits this run

- `7b020ee012daa8d9f5fb6869f339783c07891714` — fail closed on ambiguous Prometheus acceptance samples
- `f1bc9473804ebe280dc092ae22bba1596396930c` — test strict Prometheus safety query parsing

### Tests / checks / results

- Verified through the GitHub API that the new parser is present on `main` after commit and that the acceptance script routes query results through the strict parser.
- Attempted a fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` followed by the focused unittest module.
- The execution environment again failed before checkout with `Could not resolve host: github.com`; therefore the exact committed Python tests did not execute and no green claim is made.
- The full Docker observability rehearsal remains unexecuted in this environment for the same checkout/Docker-path limitation.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Treat unexpected Prometheus metric cardinality as invalid safety evidence. The acceptance harness must not choose an arbitrary series when it expects one authoritative watchdog value.
2. Require Prometheus result-shape identity (`vector`) instead of loosely traversing whatever successful response happens to contain `result`.
3. Reject non-finite samples explicitly because watchdog state and telemetry age must always be finite quantities.
4. Preserve empty-vector-as-`None` semantics so normal ingestion startup/outage polling can continue until bounded timeout; structural ambiguity remains an exception and is never accepted as success.
5. Keep this hardening dependency-free and local; it adds no service, credential, network destination, or CI workload.

### Blockers / unknowns

- The focused unit tests still need execution from a runnable checkout.
- The full Docker watchdog rehearsal still needs to run against the pinned Prometheus 3.13.3 and Grafana 13.2.1 images. It must attest live versions, then prove deadline firing/resolution and stale-telemetry firing/resolution using the new strict Prometheus evidence parser.
- Container digests are still not committed because an authoritative registry digest has not been verified through the available execution path.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity.
- Cloud Storage Policy Troubleshooter and live Gemini/Vertex acceptance still require authorized disposable-project credentials.

## Single best next step

**Run the complete credential-free Docker observability rehearsal on the first environment with a runnable checkout. In addition to live version attestation and both alert lifecycles, deliberately create or inject a duplicate watchdog series during a negative acceptance case and confirm the strict parser refuses to produce a PASS. This will validate that cardinality drift cannot make StageGuard select an arbitrary healthy-looking safety sample.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the new watchdog freshness acceptance path, explicit image pins, live runtime-version attestation, and strict Prometheus safety-query parsing.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
