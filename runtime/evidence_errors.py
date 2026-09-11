#!/usr/bin/env python3
"""Adapter-neutral evidence availability contract for StageGuard.

Expected transport/protocol/data-source failures should cross the investigator
boundary as ``EvidenceUnavailable``. Programming and policy errors intentionally
remain ordinary exceptions so they are never hidden as an operational abstention.
"""
from __future__ import annotations


class EvidenceUnavailable(RuntimeError):
    """Raised when a bounded evidence source cannot provide trustworthy evidence.

    Messages are for local diagnostics only. Incident reports must not copy the
    exception text because adapters may include provider/tool details.
    """
