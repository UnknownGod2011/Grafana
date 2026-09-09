#!/usr/bin/env python3
"""Execution-safe StageGuard service with authenticated audit-anchor restore.

This composition keeps the remediation dispatch/reconciliation barriers from
ExecutionSafeIncidentService while adding the bounded-suffix audit verification
and save-before-promote anchor lifecycle from AnchoredIncidentService.
"""
from __future__ import annotations

from anchored_incident_service import AnchoredIncidentService
from execution_safety import ExecutionSafeIncidentService


class AnchoredExecutionSafeIncidentService(
    AnchoredIncidentService,
    ExecutionSafeIncidentService,
):
    """Production-oriented composition of anchor integrity and execution safety.

    Both parents use cooperative ``super()``. The MRO is intentionally:
    AnchoredIncidentService -> ExecutionSafeIncidentService -> IncidentService,
    so anchor initialization happens before execution-safety initialization and
    both layers reach the stable IncidentService exactly once.
    """

    pass
