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

The smoke client launches `grafana/mcp-grafana:1.1.0` in stdio mode via Docker Compose, initializes MCP, verifies that `list_datasources` and `query_prometheus` are advertised as read-only tools, then executes this instant query through Grafana:

```promql
network_packet_loss_percent{production_id="broadcast-alpha",uplink="uplink-b"}
```

With the default faulted fixture, the returned value should be approximately `18`. The MCP service is constrained with `--disable-write`, only the `datasource,prometheus` categories are enabled, and proxied tools are disabled.

If an MCP protocol upgrade is required, override `STAGEGUARD_MCP_PROTOCOL_VERSION`. If Docker is not the desired client launcher, override `STAGEGUARD_MCP_COMMAND`.

## Bounded incident investigator

`investigator.py` is the deterministic policy/evidence core that sits between telemetry tools and any Gemini reasoning layer. It has a deliberately tiny read-only boundary (`MetricQueryClient.instant`) and executes exactly six fixed PromQL reads covering four required evidence classes:

1. **Symptom** — Camera 3 dropped-frame rate is elevated.
2. **Causal** — `uplink-b` packet loss is elevated.
3. **Contradiction** — Camera 3 encoder CPU and GPU are both healthy, arguing against encoder saturation.
4. **Healthy peer** — `uplink-a` and Cameras 1/2 remain healthy.

The policy will only emit the seeded high-confidence diagnosis when all four classes are present and support it. Missing telemetry produces `status="abstain"`; it never substitutes an LLM guess for absent evidence. A real symptom with contradictory causal evidence also abstains. A healthy symptom metric returns `status="no_incident"`.

This split is intentional: Gemini can later decide *which incident workflow to invoke, summarize the evidence, and communicate with operators*, while the production-safety invariant stays deterministic and testable.

## Official MCP metric adapter

`mcp_metric_client.py` now implements `MetricQueryClient` over the official Grafana MCP stdio transport. It initializes one MCP session, checks that `query_prometheus` advertises `readOnlyHint=true`, executes only instant PromQL queries, and records per-query latency/value provenance in `QueryTrace`.

The parser follows the pinned `mcp-grafana v1.1.0` implementation rather than inventing a private schema: ordinary tool values are JSON-marshaled into MCP text content, and `query_prometheus` returns a `QueryPrometheusResult` with `data`, optional `hints`, and `warnings`. The adapter also accepts `structuredContent` defensively for forward compatibility.

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

No third-party Python packages are required for the current runtime tests:

```bash
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/bootstrap_grafana.py runtime/mcp_smoke.py runtime/mcp_metric_client.py runtime/investigator.py
```

`test_investigator.py` covers the successful four-evidence diagnosis, healthy state, missing causal evidence, missing contradiction evidence, contradictory cause evidence, and the fixed six-query budget.

`test_mcp_metric_client.py` covers the pinned Prometheus vector shape, scalar shape, empty results, structured-content compatibility, multiple-series rejection, tool errors, and malformed values without requiring a live Grafana instance.

## Next implementation step

Execute the full local stack on a Docker-capable host and run `mcp_smoke.py`, then run the bounded investigator through `McpPrometheusMetricClient` and capture all six `QueryTrace` records. If that succeeds, implement the next safety boundary: a human-approved remediation command model plus telemetry-based recovery verification that cannot be satisfied by a successful action response alone.
