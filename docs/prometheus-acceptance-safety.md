# Prometheus acceptance safety

StageGuard treats Prometheus as safety evidence during the local observability rehearsal. A watchdog query is therefore accepted only when the HTTP API returns a successful instant vector with zero or one finite sample. Empty vectors may be retried during bounded polling; malformed, non-finite, or multi-series responses are invalid evidence.

## Cardinality ambiguity probe

`runtime/watchdog_observability_acceptance.py` contains a live negative probe that runs after Prometheus has ingested the healthy watchdog metric and before the alert lifecycles begin.

The probe asks Prometheus to create two label-distinct views of the same source series at query time:

```promql
label_replace(stageguard_remediation_execution_deadline_exceeded, "stageguard_acceptance_probe", "left", "", "")
or
label_replace(stageguard_remediation_execution_deadline_exceeded, "stageguard_acceptance_probe", "right", "", "")
```

The `label_replace()` calls add different values for the synthetic `stageguard_acceptance_probe` label. Prometheus's `or` set operator returns the union of instant-vector elements whose label sets do not match, so a healthy single source series becomes two returned series. StageGuard must reject that response with its explicit `exactly one series` guard. If it accepts a value, the entire observability rehearsal fails.

This design deliberately does **not** change the fixture exposition or write synthetic samples into Prometheus. Injecting persistent duplicate series can leave stale series queryable after the negative case and make immediate local reruns nondeterministic. The query-local probe exercises the real Prometheus HTTP query path and real vector cardinality semantics without leaving residual time series.

## Why fail closed

The watchdog signal is expected to have one authoritative value. If labels, scrape topology, federation, remote-write replay, or configuration drift causes more than one series to match, selecting an arbitrary element would make result ordering part of the safety decision. StageGuard instead treats cardinality drift as an evidence-integrity failure.

This does not replace production telemetry hygiene. Real deployments should still scope labels and recording/alert rules so each intended runtime identity has a deterministic watchdog series. The acceptance rule exists to prevent accidental ambiguity from being silently interpreted as healthy.

## References

- Prometheus query operators: https://prometheus.io/docs/prometheus/latest/querying/operators/
- Prometheus `label_replace()` function: https://prometheus.io/docs/prometheus/latest/querying/functions/#label_replace
- Prometheus HTTP query API: https://prometheus.io/docs/prometheus/latest/querying/api/
