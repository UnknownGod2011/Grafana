# Runtime metrics ingestion

StageGuard exposes runtime safety metrics at `/metrics`, including the remediation execution watchdog used by the source-controlled Grafana dashboard and alerts. Production Cloud Run services should remain authenticated; do **not** make the service public merely so Prometheus can scrape it.

## Local rehearsal

The default Docker Compose stack includes a credential-free `watchdog-fixture` service. Prometheus scrapes it as `stageguard-runtime-watchdog`, so the `StageGuard Runtime Safety` dashboard has realistic watchdog series even when the full incident API is not running.

The fixture has only three named states and is not a remediation provider:

```bash
# idle / healthy watchdog
curl -X POST http://127.0.0.1:9111/scenario/idle

# in-flight but below the deadline
curl -X POST http://127.0.0.1:9111/scenario/active

# deterministic deadline-exceeded signal
curl -X POST http://127.0.0.1:9111/scenario/overdue
```

Prometheus should then expose all four series:

```promql
stageguard_remediation_execution_active
stageguard_remediation_execution_age_seconds
stageguard_remediation_execution_max_seconds
stageguard_remediation_execution_deadline_exceeded
```

The Grafana-managed `stageguard-remediation-deadline` rule evaluates the last series. It intentionally treats missing telemetry as `NoData`, not as a synthetic deadline breach.

### Freshness is independent from watchdog value

A stored `stageguard_remediation_execution_deadline_exceeded 0` is only meaningful while the telemetry path is still delivering fresh samples. The runtime dashboard therefore also computes sample age from Prometheus timestamps:

```promql
max(time() - timestamp(stageguard_remediation_execution_deadline_exceeded))
or vector(1000000000) * absent(stageguard_remediation_execution_deadline_exceeded)
```

Prometheus documents `time()` as the evaluation timestamp, `timestamp()` as the source sample timestamp, and `absent()` as a way to detect a missing series. StageGuard uses those primitives to keep two conditions separate:

- `stageguard-remediation-deadline` means a fresh watchdog sample positively reports that execution exceeded its configured bound;
- `stageguard-runtime-telemetry-stale` means the evidence plane itself is stale or missing, so an old healthy value must not be trusted.

The stale-telemetry rule enters warning after the newest watchdog deadline sample is more than 45 seconds old and remains so for 30 seconds. A completely absent series is mapped to a deliberately enormous sample age by the query, so missing telemetry follows the same bounded stale-evidence path instead of masquerading as healthy. This rule does not replay remediation, change incident state, or grant Grafana any write credential.

After `docker compose up --build -d`, run the bounded acceptance rehearsal:

```bash
python runtime/watchdog_observability_acceptance.py
```

The script proves the complete watchdog alert lifecycle rather than only the firing edge:

1. force the fixture to `idle` and wait until Prometheus reports `deadline_exceeded=0`;
2. move the fixture to `overdue` and wait for Prometheus to ingest `1`;
3. wait for the Grafana-managed watchdog alert to appear in Grafana's active Alertmanager v2 alerts response;
4. return the fixture to `idle` and wait for Prometheus to report `0` again;
5. require that the StageGuard watchdog alert disappears from the valid active-alert response, proving resolution rather than merely assuming it from the metric transition.

Unexpected Grafana response shapes are never interpreted as recovery. The parser accepts only an active-alert list and fails closed on malformed alert entries, so an API/schema failure cannot produce a false PASS. Unrelated active alerts may remain present; only the StageGuard watchdog rule is required to resolve. The fixture is also reset to `idle` in a `finally` block.

All three service endpoints are required to be loopback HTTP origins so the local default Grafana credentials cannot be sent to a remote host by mistake. The default firing and resolution waits are bounded and can be adjusted with `--alert-timeout` and `--resolve-timeout` when testing a deliberately slower local evaluation interval.

## Authenticated Cloud Run scrape bridge

`runtime/cloud_run_metrics_bridge.py` is a narrow identity-aware bridge for Prometheus-compatible collectors. It obtains a short-lived Google-signed ID token with Application Default Credentials and forwards **only** `GET /metrics` to one configured HTTPS service origin.

Safety boundaries:

- the upstream target must be an HTTPS origin with no user info, arbitrary path, query, or fragment;
- the bridge never forwards caller headers;
- the bridge owns the `Authorization: Bearer <ID token>` header;
- upstream response size is bounded;
- upstream exceptions and response bodies are not returned to the scraper;
- the default listener is loopback-only;
- a non-loopback bind requires explicit `--allow-network-bind`, intended only for a trusted private container/VPC network;
- the bridge has no remediation, lifecycle, generic proxy, or arbitrary-fetch endpoint.

Run it on a Google Cloud workload or another environment where ADC can mint an ID token for the StageGuard Cloud Run service:

```bash
python runtime/cloud_run_metrics_bridge.py \
  --target https://STAGEGUARD_SERVICE_HOST \
  --host 127.0.0.1 \
  --port 9112
```

`--target` may also be supplied through `STAGEGUARD_METRICS_TARGET`. `STAGEGUARD_METRICS_AUDIENCE` is available only for deployments where the accepted Cloud Run audience differs from the target origin. Keep it an HTTPS service origin.

A local Prometheus process can then scrape:

```yaml
scrape_configs:
  - job_name: stageguard-runtime
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:9112"]
```

If Prometheus and the bridge run in separate containers, bind the bridge to the private container network with `--host 0.0.0.0 --allow-network-bind` and do **not** publish that bridge port to an untrusted host/network.

## Required Google Cloud identity

The bridge's workload identity needs permission to invoke the StageGuard Cloud Run service (normally `roles/run.invoker`). Prefer an attached service account for workloads running on Google Cloud. For workloads outside Google Cloud, prefer Workload Identity Federation rather than a long-lived service-account key.

Google's Cloud Run service-to-service authentication documentation describes obtaining an ID token for the target service audience with Application Default Credentials. StageGuard follows that model rather than storing a static bearer token in Prometheus configuration.

References:

- Google Cloud — Authenticate service-to-service requests: https://cloud.google.com/run/docs/authenticating/service-to-service
- Google Cloud — Get an ID token: https://cloud.google.com/docs/authentication/get-id-token
- Prometheus — Query functions (`time`, `timestamp`, `absent`): https://prometheus.io/docs/prometheus/latest/querying/functions/
- Prometheus — scrape configuration / authorization: https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- Grafana — Prometheus alerting, including missing/stale metric patterns: https://grafana.com/docs/grafana/latest/datasources/prometheus/alerting/
- Grafana — Alerting provisioning: https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/
- Grafana — View active notifications: https://grafana.com/docs/grafana/latest/alerting/monitor-status/view-active-notifications/

## Grafana Cloud / remote Prometheus

For Grafana Cloud or any remote Prometheus-compatible backend, keep the same trust split: run the identity-aware bridge or an equivalent collector close to the authenticated Cloud Run service, then send/scrape only metrics through the monitoring plane. Do not give Grafana or Grafana MCP the remediation provider credential.

If remote write is used, configure it on the collector/Prometheus side with the backend's supported authentication and secret store. StageGuard's repository intentionally does not embed a Grafana Cloud URL, tenant ID, API token, notification destination, or Cloud Run invoker credential.
