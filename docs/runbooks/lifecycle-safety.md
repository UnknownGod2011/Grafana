# StageGuard lifecycle-safety runbook

Use this runbook when the Grafana alert `stageguard-lifecycle-unsafe` fires or the **StageGuard Lifecycle Safety** dashboard reports an unsafe or missing lifecycle state.

## Safety rule

Treat the lifecycle boundary as fail-closed. Do **not** replay remediation, bypass approval, edit checkpoint state, or infer recovery from provider acceptance. Recovery requires fresh Grafana evidence and StageGuard's normal recovery-verification path.

## 1. Establish evidence availability

1. Open **StageGuard Lifecycle Safety** in Grafana.
2. Confirm **Runtime evidence transport** is healthy and **Lifecycle telemetry freshness** is current.
3. If telemetry is absent/stale, treat this as evidence loss. Restore the StageGuard runtime scrape / metrics bridge before diagnosing lifecycle state from Grafana.
4. Check `/readyz`. An unsafe lifecycle invariant is expected to withdraw readiness.

Do not interpret a missing Prometheus series as `ok`.

## 2. Identify the authoritative lifecycle state

Use the dashboard's **Lifecycle state timeline**. `stageguard_lifecycle_safety_state` is the authoritative one-hot metric; Grafana must not reconstruct the application state machine.

Typical unsafe reasons are:

- checkpoint conflict;
- audit-integrity failure;
- execution uncertainty;
- a combination of the above.

Capture the incident/revision/operation identifiers and the relevant Grafana time range before changing anything.

## 3. Investigate by state

### Checkpoint conflict

Compare the durable checkpoint with the authenticated lifecycle state and audit trail. Determine which revision/operation is authoritative. Do not hand-edit the checkpoint to make the alert disappear. Resolve through the application's supported reconciliation/recovery path.

### Audit-integrity failure

Preserve the audit material. Verify ordering/integrity evidence and storage availability. Do not approve or execute new remediation while the audit boundary is invalid. If corruption is suspected, retain the affected files/objects for forensic review rather than rewriting them.

### Execution uncertainty

Assume the provider may have accepted the operation even if StageGuard did not receive a definitive response. Use the remediation adapter's **read-only operation reconciliation** with the canonical operation ID. Do not issue a second write to discover whether the first write happened.

If reconciliation proves the operation was not accepted, return through the normal approval/execution state machine. If it proves acceptance, proceed to fresh telemetry recovery verification; provider acceptance alone is not recovery.

### Combined unsafe state

Resolve every represented invariant. Clearing only one condition must not be treated as lifecycle recovery while another unsafe state remains active.

## 4. Verify recovery

1. Restore/confirm fresh Grafana evidence.
2. Run StageGuard's recovery verification; do not substitute a provider response for telemetry proof.
3. Confirm `stageguard_recovery_verified` reflects the expected recovery outcome when recovery is applicable.
4. Confirm `stageguard_lifecycle_safety_state{state="ok"}` is the active one-hot state and non-`ok` states are zero.
5. Confirm `/readyz` returns healthy only after the application has cleared the safety boundary.
6. Confirm `stageguard-lifecycle-unsafe` returns to Normal after fresh samples arrive.

## 5. Evidence to retain

Retain the Grafana time range/snapshot, incident and revision identifiers, canonical remediation operation ID (if any), checkpoint/reconciliation outcome, audit-integrity result, and recovery-verification evidence. Never copy bearer tokens, provider credentials, API keys, or authorization headers into incident notes.

## Escalation criteria

Escalate rather than attempting manual mutation when durable state disagrees after reconciliation, audit integrity cannot be established, the remediation provider cannot answer read-only operation status, telemetry remains unavailable, or the lifecycle state remains unsafe after its underlying condition is resolved.

## Local acceptance

For maintainers with an executable Docker checkout, validate the integrated observability path with:

```bash
python scripts/run_stageguard_validation.py --require-full-coverage --keep-going
python scripts/demo_release.py --non-interactive
```

The rehearsal must leave Grafana read-only with respect to remediation. The official Grafana MCP integration is an evidence/query plane, not an infrastructure-write credential path.
