#!/usr/bin/env python3
"""Opt-in, state-isolated Vertex AI Gemini acceptance smoke test for StageGuard.

This command is intentionally separate from StageGuard incident execution. By default it
performs configuration validation only. A single paid/model request is made only when
--execute is supplied. The request contains no incident data, Grafana data, credentials,
remediation instructions, or StageGuard state and cannot mutate production resources.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_LOCATION = "global"
DEFAULT_MODEL = "gemini-2.5-flash"
_LOCATION_RE = re.compile(r"^[a-z0-9-]+$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


@dataclass(frozen=True)
class SmokePlan:
    project: str
    location: str
    model: str
    execute: bool


def _resolve_plan(args: argparse.Namespace) -> SmokePlan:
    project = (args.project or os.getenv("GOOGLE_CLOUD_PROJECT", "")).strip()
    location = (args.location or os.getenv("GOOGLE_CLOUD_LOCATION", DEFAULT_LOCATION)).strip() or DEFAULT_LOCATION
    model = (args.model or os.getenv("STAGEGUARD_GEMINI_MODEL", DEFAULT_MODEL)).strip() or DEFAULT_MODEL

    if not project:
        raise ValueError("GOOGLE_CLOUD_PROJECT (or --project) is required")
    if not _PROJECT_RE.fullmatch(project):
        raise ValueError("project must be a Google Cloud project ID, not a number, URL, or resource path")
    if not _LOCATION_RE.fullmatch(location):
        raise ValueError("location must be a plain Vertex AI location identifier")
    if not _MODEL_RE.fullmatch(model):
        raise ValueError("model must be a plain publisher model identifier")
    return SmokePlan(project=project, location=location, model=model, execute=bool(args.execute))


def _execute_smoke(plan: SmokePlan) -> dict[str, Any]:
    """Perform exactly one bounded generateContent request and validate its JSON response."""
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError as exc:
        raise RuntimeError("install google-genai to run the live Gemini acceptance smoke test") from exc

    client = genai.Client(vertexai=True, project=plan.project, location=plan.location)
    response = client.models.generate_content(
        model=plan.model,
        contents=(
            "Return a JSON object with status set to ok and purpose set to "
            "stageguard-gemini-acceptance. This is only a connectivity check."
        ),
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=48,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "status": {"type": "STRING", "enum": ["ok"]},
                    "purpose": {"type": "STRING", "enum": ["stageguard-gemini-acceptance"]},
                },
                "required": ["status", "purpose"],
            },
        ),
    )

    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Gemini returned no acceptance response")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini returned non-JSON acceptance output") from exc
    if payload != {"status": "ok", "purpose": "stageguard-gemini-acceptance"}:
        raise RuntimeError("Gemini acceptance response did not match the locked smoke schema")

    return {
        "status": "ok",
        "purpose": "stageguard-gemini-acceptance",
        "request_count": 1,
        "state_mutation": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate StageGuard Vertex/Gemini configuration; add --execute to make one "
            "state-isolated generateContent acceptance request."
        )
    )
    parser.add_argument("--project", help="Google Cloud project ID; defaults to GOOGLE_CLOUD_PROJECT")
    parser.add_argument("--location", help=f"Vertex AI location; defaults to GOOGLE_CLOUD_LOCATION or {DEFAULT_LOCATION}")
    parser.add_argument("--model", help=f"Gemini model; defaults to STAGEGUARD_GEMINI_MODEL or {DEFAULT_MODEL}")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="make exactly one live generateContent request; without this flag no model request is sent",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        plan = _resolve_plan(args)
    except ValueError as exc:
        if args.json:
            print(json.dumps({"status": "invalid", "error": str(exc)}, sort_keys=True))
        else:
            print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    result: dict[str, Any] = {
        "status": "validated",
        "plan": asdict(plan),
        "request_count": 0,
        "state_mutation": False,
        "note": "No model request sent. Add --execute only after gcp_deploy_doctor.py passes live checks.",
    }

    if plan.execute:
        try:
            live = _execute_smoke(plan)
        except Exception as exc:  # noqa: BLE001 - CLI must fail closed with concise operator output
            result = {
                "status": "failed",
                "plan": asdict(plan),
                "request_count": 1,
                "state_mutation": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            if args.json:
                print(json.dumps(result, sort_keys=True))
            else:
                print(f"FAILED: {result['error']}", file=sys.stderr)
            return 1
        result = {"plan": asdict(plan), **live}

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        if plan.execute:
            print(f"PASS: one Gemini generateContent request succeeded with {plan.model} in {plan.location}")
        else:
            print("PASS: configuration validated; no Gemini request was sent")
            print("Next: run scripts/gcp_deploy_doctor.py --json, then rerun this command with --execute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
