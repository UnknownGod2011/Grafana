# Watchdog scrape health

StageGuard separates **transport/scrape health** from **runtime safety evidence**.

The Prometheus job `stageguard-runtime-watchdog` scrapes the watchdog metrics endpoint. Prometheus attaches the configured job name as the `job` label, so StageGuard can use the generated target-health series:

```promql
up{job="stageguard-runtime-watchdog"}
```

The runtime-safety dashboard renders:

```promql
min(up{job="stageguard-runtime-watchdog"})
```

and the Grafana-managed warning rule evaluates:

```promql
max(up{job="stageguard-runtime-watchdog"}) < 0.5
```

for 20 seconds. `NoData` is also alerting, because a missing target-health series is not evidence that the watchdog path is healthy.

## Why this is separate from telemetry freshness

The existing freshness rule remains the fail-safe evidence rule:

```promql
max(time() - timestamp(stageguard_remediation_execution_deadline_exceeded))
  or vector(1000000000) * absent(stageguard_remediation_execution_deadline_exceeded)
```

These signals answer different questions:

- **scrape health (`up`)** — can Prometheus currently scrape the watchdog target? This is fast operational diagnosis for bridge/IAM/network/service failures.
- **sample freshness** — is the watchdog safety sample still recent enough to trust? This remains authoritative when deciding whether a previous healthy value has become stale.
- **deadline exceeded** — did StageGuard positively report that a remediation execution exceeded its configured safety deadline?

A scrape failure must never be reclassified as a positive remediation deadline breach. During a transport outage operators should treat runtime safety evidence as degraded/unknown until ingestion recovers.

For the local fixture, `POST /telemetry/offline` makes `/metrics` fail while leaving control endpoints healthy. This provides a deterministic path for rehearsing both the immediate scrape-health warning and the later stale-evidence warning without mutating remediation state.

## Production mapping

For private Cloud Run deployments, the target should be the loopback/default-safe authenticated metrics bridge (or another trusted identity-aware collector), not a publicly exposed StageGuard service. A scrape-health alert therefore helps localize failures across the collector, identity/IAM path, network path, and authenticated `/metrics` readiness before the sample-age alert matures.

## References

- Prometheus, *First steps with Prometheus*: Prometheus collects target metrics by scraping configured HTTP endpoints and evaluates rules on the collected data: https://prometheus.io/docs/introduction/first_steps/
- Prometheus, *Getting started*: a configured `job_name` is attached as the `job` label to time series scraped from that target: https://prometheus.io/docs/prometheus/latest/getting_started/
