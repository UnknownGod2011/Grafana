# Authenticated audit anchors

StageGuard's audit hash chain can grow for the lifetime of an incident, while Cloud Logging queries are intentionally bounded by lookback and result-count limits. Rolling anchors let production restart verify a bounded suffix without turning old log retention into an availability dependency.

## Trust model

An audit anchor is a previously verified `(sequence, head_sha256)` chain checkpoint. The anchor is **not** trusted merely because it exists in a log or local file. Production may trust it only after it has been embedded in the same HMAC-authenticated durable checkpoint envelope that protects lifecycle state.

The current checkpoint chain head remains the commit marker. On restart, StageGuard reconstructs only the events in `(anchor.sequence, current.sequence]` and uses the current authenticated head to select the exact winning lineage through any append-before-CAS competitors.

This gives three useful properties:

- audit records at or before the authenticated anchor may age out or be compacted without making healthy restart impossible;
- deletion, mutation, or substitution inside the post-anchor committed suffix still fails integrity verification closed;
- losing-writer records after the anchor remain forensic residue and cannot manufacture approval, remediation, recovery, or operator timeline state.

## Bounds

`runtime/audit_anchor.py` currently defines a default roll interval of 1024 committed events and a maximum verification suffix of 2048 sequence positions. These are safety defaults, not external API limits. A deployment should roll early enough that the post-anchor candidate set remains comfortably below the Cloud Logging candidate cap even when same-sequence loser records exist.

Cloud Logging candidate reads now accept an exclusive `after_sequence` lower bound, allowing the query itself to request only the post-anchor suffix. The filter still constrains the configured log name, StageGuard audit schema, incident ID, timestamp lookback, and authenticated sequence range.

Google's Cloud Logging guidance recommends constraining queries by log name and narrow time windows for efficient retrieval; StageGuard already does both and now additionally constrains the audit sequence range. See the official Cloud Logging query-language documentation referenced in project research notes/run history.

## Safe roll procedure

1. Start from an anchor already authenticated by durable checkpoint state, or genesis for a new incident.
2. Verify/advance the normal audit chain through committed lifecycle writes.
3. Once the configured interval is reached, derive the next anchor from the **already verified current chain checkpoint**.
4. Persist that anchor together with the current chain head inside one authenticated lifecycle checkpoint CAS.
5. Only after that checkpoint is durable may records at or before the new anchor be treated as compactable/retention-independent.

Never create an anchor from an unauthenticated Cloud Logging record, a browser value, a remediation response, or a losing writer's append. Never move an anchor backward. Never substitute a different head at the same sequence.

## Integration status

The anchor primitive, bounded suffix verifier, and ranged Cloud Logging candidate reader are implemented with credential-free regression tests. The remaining integration step is checkpoint schema/runtime wiring: persist the rolling anchor in authenticated checkpoint state and make `IncidentService` restore call the ranged reader with `after_sequence=anchor.sequence` before selecting the committed suffix.
