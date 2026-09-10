#!/usr/bin/env python3
"""Pure validators for StageGuard Google Cloud deployment identifiers.

The module intentionally performs no network calls and reads no secrets. It is
shared by deployment tooling so Cloud Run preflight and the deployment command
accept the same resource identifiers.
"""
from __future__ import annotations

import argparse
import re


PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
SERVICE_NAME_RE = re.compile(r"^[a-z](?:[a-z0-9-]{0,47}[a-z0-9])?$")
REGION_RE = re.compile(r"^[a-z][a-z0-9-]{0,62}[a-z0-9]$")
ARTIFACT_REGISTRY_IMAGE_RE = re.compile(
    r"^(?P<location>[a-z][a-z0-9-]{0,62}[a-z0-9])-docker\.pkg\.dev/"
    r"(?P<project>[a-z][a-z0-9-]{4,28}[a-z0-9])/"
    r"(?P<repository>[a-z0-9][a-z0-9._-]{0,127})/"
    r"(?P<image>[a-z0-9][a-z0-9._/-]{0,255})"
    r"(?:(?::(?P<tag>[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}))|"
    r"(?:@sha256:(?P<digest>[0-9a-f]{64})))$"
)


def valid_project_id(value: str) -> bool:
    """Validate the documented modern Google Cloud project-ID grammar."""
    return bool(PROJECT_ID_RE.fullmatch(value))


def valid_service_name(value: str) -> bool:
    """Validate a Cloud Run service name (1-49 chars, lowercase DNS-like ID)."""
    return bool(SERVICE_NAME_RE.fullmatch(value))


def valid_region(value: str) -> bool:
    """Validate a bounded Google Cloud region/location identifier shape."""
    return bool(REGION_RE.fullmatch(value) and "-" in value)


def parse_artifact_registry_image(value: str) -> re.Match[str] | None:
    """Parse a tagged or sha256-pinned Artifact Registry Docker image URI."""
    return ARTIFACT_REGISTRY_IMAGE_RE.fullmatch(value)


def valid_artifact_registry_image(value: str) -> bool:
    return parse_artifact_registry_image(value) is not None


def image_is_digest_pinned(value: str) -> bool:
    match = parse_artifact_registry_image(value)
    return bool(match and match.group("digest"))


def image_project(value: str) -> str | None:
    match = parse_artifact_registry_image(value)
    return match.group("project") if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--service-name", required=True)
    parser.add_argument("--image-url", required=True)
    args = parser.parse_args()

    failures: list[str] = []
    if not valid_project_id(args.project_id):
        failures.append("PROJECT_ID must be 6-30 lowercase letters, digits, or hyphens, start with a letter, and not end with a hyphen")
    if not valid_region(args.region):
        failures.append("REGION must be a bounded lowercase Google Cloud region/location identifier")
    if not valid_service_name(args.service_name):
        failures.append("SERVICE_NAME must be 1-49 lowercase letters, digits, or hyphens, start with a letter, and not end with a hyphen")
    if not valid_artifact_registry_image(args.image_url):
        failures.append("IMAGE_URL must be a tagged or sha256-pinned Artifact Registry Docker image URI")

    if failures:
        for failure in failures:
            print(failure)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
