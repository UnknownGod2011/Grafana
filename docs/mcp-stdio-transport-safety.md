# Grafana MCP stdio transport safety

StageGuard treats Grafana MCP as a local, read-only evidence subprocess. Production metric and Loki adapters therefore support **stdio transport only**.

This is a deliberate security boundary, not merely a launcher preference.

## Why StageGuard enforces stdio

The official `grafana/mcp-grafana` project supports three transports: `stdio`, `sse`, and `streamable-http`. Its native binary defaults to `stdio`, but the official Docker image uses a network transport by default unless `-t stdio` is supplied explicitly.

Upstream references reviewed for the pinned `v1.4.1` release (published 2026-09-11):

- Release: https://github.com/grafana/mcp-grafana/releases/tag/v1.4.1
- Upstream README / CLI flags: https://github.com/grafana/mcp-grafana/blob/v1.4.1/README.md
- Upstream Docker usage explicitly notes that `-t stdio` overrides the Docker image's default SSE mode.

Network transports add a materially different trust boundary: listener binding, Host/Origin policy, and caller authentication all become part of the MCP security model. StageGuard does not need that surface because its evidence adapters spawn the MCP process locally and communicate over stdin/stdout.

## Enforced launcher policy

`runtime/command_line.py` is the shared launcher boundary used by the production Prometheus and Loki MCP adapters.

It now fails closed when `STAGEGUARD_MCP_COMMAND`:

- explicitly selects `sse`;
- explicitly selects `streamable-http`;
- selects any unknown non-stdio transport;
- declares the transport more than once;
- supplies a transport flag without a value; or
- directly launches `grafana/mcp-grafana:<tag>` or `grafana/mcp-grafana@<digest>` without explicitly declaring `-t stdio` / `--transport stdio`.

The native `mcp-grafana` binary may omit `-t stdio` because upstream documents stdio as the native CLI default.

The repository's reference launcher remains:

```text
docker compose run --rm -T mcp
```

That command is accepted because `docker-compose.yml` owns the actual MCP container configuration and already pins:

```text
-t stdio
--disable-write
--enabled-tools datasource,prometheus,loki
--disable-proxied
```

The Compose MCP service does not publish an MCP network port.

## Safe custom launcher examples

Native binary:

```text
STAGEGUARD_MCP_COMMAND="mcp-grafana --disable-write -t stdio"
```

Direct official Docker image:

```text
STAGEGUARD_MCP_COMMAND="docker run --rm -i grafana/mcp-grafana:1.4.1 -t stdio --disable-write"
```

The second form still requires the operator to provide the appropriate Grafana URL and credential environment/secret mounts. The transport interlock does not replace least-privilege Grafana credentials or `--disable-write`.

## Threat model

Without this interlock, a seemingly harmless launcher override such as:

```text
docker run --rm grafana/mcp-grafana:1.4.1
```

can change the MCP process from a private stdio peer into a network server because the Docker image's transport default differs from the native binary default. Even if StageGuard itself never connects successfully, the child process could listen until the request timeout and cleanup path terminates it.

StageGuard therefore rejects that configuration **before spawning the subprocess**.

This keeps the evidence plane's transport invariant local and reviewable: the Python runtime never intentionally opens an MCP listener, never depends on browser-origin policy for MCP security, and never needs to expose a caller-authenticated MCP endpoint merely to query Grafana.

## Regression contract

`runtime/tests/test_command_line.py` locks:

- native-binary stdio default acceptance;
- repository Compose launcher acceptance;
- direct official Docker image rejection without explicit stdio;
- tagged and digest image handling;
- all supported explicit stdio flag forms;
- SSE and streamable-HTTP rejection;
- unknown transport rejection;
- duplicate transport rejection; and
- missing transport-value rejection.

Future support for a network MCP transport must be an explicit architecture change. It would require a separate threat model for listener binding, authentication, Host/Origin validation, TLS, reverse-proxy trust, and credential forwarding rather than weakening this parser boundary.