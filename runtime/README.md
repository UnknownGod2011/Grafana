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

## Gate A PromQL evidence set

```promql
rate(video_frames_dropped_total{production_id="broadcast-alpha",feed_id="cam-3"}[1m])
```

```promql
encoder_cpu_percent{production_id="broadcast-alpha",feed_id="cam-3"}
```

```promql
encoder_gpu_percent{production_id="broadcast-alpha",feed_id="cam-3"}
```

```promql
network_packet_loss_percent{production_id="broadcast-alpha"}
```

```promql
sum by (feed_id) (rate(video_frames_dropped_total{production_id="broadcast-alpha"}[1m]))
```

The fixture exposes four evidence classes: Camera 3 symptom, `uplink-b` causal signal, normal Camera 3 encoder utilization as contradiction evidence, and healthy Camera 1/2 peers.

## Tests

No third-party Python packages are required for the simulator tests:

```bash
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/bootstrap_grafana.py runtime/mcp_smoke.py
```

The next implementation step after Gate A passes is a bounded StageGuard investigation agent that executes the four evidence queries through MCP, scores evidence completeness, and abstains when required evidence is missing.
