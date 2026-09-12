# Local runtime

This directory is the executable StageGuard vertical slice. It is intentionally local/free and requires no cloud credentials.

## Start the telemetry stack

```bash
docker compose up --build -d
```

Endpoints:

- Simulator metrics: `http://localhost:9108/metrics`
- Simulator state: `http://localhost:9108/state`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (`admin` / `stageguard-local-only`)

Grafana is provisioned with a Prometheus datasource UID of `stageguard-prometheus`.

## Replay the deterministic incident

The stack starts faulted by default. Reset to healthy, then inject again:

```bash
curl -X POST http://localhost:9108/scenario/reset
curl -X POST http://localhost:9108/scenario/fault
```

Recover without resetting counters:

```bash
curl -X POST http://localhost:9108/scenario/recover
```

## Bootstrap the read-only MCP credential

The official Grafana MCP is intentionally not started by the normal compose profile. Create a short-lived local Viewer service-account token first:

```bash
python runtime/bootstrap_grafana.py
```

The script waits for Grafana, creates/reuses the `stageguard-mcp` Viewer account, and stores the token at `runtime/.secrets/grafana-mcp-token` with owner-only permissions. The secret path is gitignored and the token value is never printed.

Safety properties:

- remote Grafana targets are refused unless `STAGEGUARD_ALLOW_REMOTE_BOOTSTRAP=1` is explicitly set;
- an existing service account is not auto-promoted or broadened;
- local tokens default to a 24-hour TTL;
- the MCP container uses `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE`, so credentials are not embedded in compose YAML or process arguments.

## Prove Gate A through official Grafana MCP

```bash
python runtime/mcp_smoke.py
```

The reference stack pins `grafana/mcp-grafana:1.4.1` in stdio mode. The smoke client initializes MCP, validates the live tool registry, requires every advertised tool to carry `annotations.readOnlyHint=true`, and then executes bounded evidence reads through Grafana. The MCP service is constrained server-side with `--disable-write`, `--disable-proxied`, and only the `datasource,prometheus,loki` categories enabled.

The smoke transport also fails closed on malformed JSON-RPC, mismatched response IDs, request timeouts, frames larger than 1 MiB, or more than 16 pending stdout frames. If an MCP protocol upgrade is required, override `STAGEGUARD_MCP_PROTOCOL_VERSION`. If Docker is not the desired client launcher, override `STAGEGUARD_MCP_COMMAND`.

## Bounded incident investigator

`investigator.py` is the deterministic policy/evidence core that sits between telemetry tools and any Gemini reasoning layer. It has a deliberately tiny read-only boundary (`MetricQueryClient.instant`) and executes exactly six fixed PromQL reads covering four required evidence classes:

1. **Symptom** — the configured affected feed has elevated dropped-frame rate.
2. **Causal** — the configured affected uplink has elevated packet loss.
3. **Contradiction** — encoder CPU and GPU are healthy, arguing against encoder saturation.
4. **Healthy peer** — an independently configured uplink and peer-feed set remain healthy.

Telemetry mappings fail closed if the healthy comparator uplink is the affected uplink, if the affected feed is included in `healthy_peer_feeds`, or if the healthy peer list contains duplicates. Those constraints keep the contradiction/peer evidence independent instead of allowing a self-referential comparison to inflate diagnosis confidence.

The policy will only emit the seeded high-confidence diagnosis when all four classes are present and support it. Missing telemetry produces `status="abstain"`; it never substitutes an LLM guess for absent evidence. A real symptom with contradictory causal evidence also abstains. A healthy symptom metric returns `status="no_incident"`.

This split is intentional: Gemini summarizes and communicates evidence, while the production-safety invariant stays deterministic and testable.

## Official MCP metric adapter

`mcp_metric_client.py` implements `MetricQueryClient` over the official Grafana MCP stdio transport. It initializes one MCP session, checks that the Prometheus query tool is read-only, executes only instant PromQL queries, and records per-query latency/value provenance in `QueryTrace`.

Safety behavior is fail-closed:

- an empty Prometheus vector becomes `None` and therefore missing evidence;
- tool errors are raised, never converted to healthy telemetry;
- malformed/non-numeric samples are rejected;
- multiple instant series are rejected rather than silently selecting one;
- the bounded investigator still owns the six-query policy and thresholds.

Once the local stack and MCP credential are ready, a real diagnosis can be executed from Python with:

```python
from investigator import investigate
from mcp_metric_client import McpPrometheusMetricClient

with McpPrometheusMetricClient() as metrics:
    report = investigate(metrics)
    print(report.to_dict())
    print(metrics.traces)
```

## Gate A PromQL evidence set

```promql
rate(video_frames_dropped_total{production_id="broadcast-alpha",feed_id="cam-3"}[2m])
```

```promql
network_packet_loss_percent{production_id="broadcast-alpha",uplink="uplink-b"}
```

```promql
encoder_cpu_percent{production_id="broadcast-alpha",feed_id="cam-3"}
```

```promql
encoder_gpu_percent{production_id="broadcast-alpha",feed_id="cam-3"}
```

```promql
network_packet_loss_percent{production_id="broadcast-alpha",uplink="uplink-a"}
```

```promql
max(rate(video_frames_dropped_total{production_id="broadcast-alpha",feed_id=~"cam-1|cam-2"}[2m]))
```

## Tests

No third-party Python packages are required for the core runtime tests:

```bash
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/bootstrap_grafana.py runtime/mcp_smoke.py runtime/mcp_metric_client.py runtime/investigator.py runtime/telemetry.py
```

`test_telemetry.py` covers custom mappings, PromQL escaping, independent healthy comparator validation, fixed query budgets, recovery windows, and missing-evidence abstention.

`test_mcp_metric_client.py` covers Prometheus result parsing, empty results, structured-content compatibility, multiple-series rejection, tool errors, and malformed values without requiring a live Grafana instance.

## Current validation priority

On a Docker-capable checkout, first run the current telemetry/MCP regression modules and the live `grafana/mcp-grafana:1.4.1` smoke. Then execute the private Cloud Run metrics acceptance path (`ADC -> /metrics -> authenticated bridge -> Prometheus up 1 -> 0 -> 1`) before treating the production observability path as release-ready.
