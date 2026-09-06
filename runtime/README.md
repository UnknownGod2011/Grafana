# Local runtime

This directory is the first executable StageGuard vertical slice. It is intentionally local/free and requires no cloud credentials.

## Start

```bash
docker compose up --build
```

Endpoints:

- Simulator metrics: `http://localhost:9108/metrics`
- Simulator state: `http://localhost:9108/state`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (`admin` / `stageguard-local-only`)

Grafana is provisioned with a datasource UID of `stageguard-prometheus` pointing at the local Prometheus instance.

## Replay the deterministic incident

The compose stack starts faulted by default. Reset to healthy, then inject again:

```bash
curl -X POST http://localhost:9108/scenario/reset
curl -X POST http://localhost:9108/scenario/fault
```

Recover without resetting counters:

```bash
curl -X POST http://localhost:9108/scenario/recover
```

## Gate A PromQL

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

The fixture deliberately exposes four evidence classes: Camera 3 symptom, uplink-b causal signal, normal Camera 3 encoder utilization as contradiction evidence, and healthy Camera 1/2 peers.

## Tests

No third-party Python packages are required:

```bash
python -m unittest discover -s runtime/tests -v
```

The next integration step is to add the official Grafana MCP as a local service/client against this provisioned Grafana datasource, then verify a real `query_prometheus` call before wiring Gemini.
