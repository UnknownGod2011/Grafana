#!/usr/bin/env python3
"""Credential-safe pre-deploy checks for StageGuard's Google Cloud runtime.

The doctor validates the deployment environment before scripts/deploy_cloud_run.sh
is invoked. It never reads secret payloads, prints access tokens, changes IAM,
enables APIs, deploys services, or mutates Google Cloud resources.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass


REQUIRED_ENV = (
    "PROJECT_ID",
    "PROJECT_NUMBER",
    "REGION",
    "SERVICE_NAME",
    "IMAGE_URL",
    "RUNTIME_SERVICE_ACCOUNT",
    "IAP_AUDIENCE",
    "GRAFANA_URL",
    "TELEMETRY_SECRET",
    "METRIC_ACTIVATION_SECRET",
    "LOG_ACTIVATION_SECRET",
    "GRAFANA_TOKEN_SECRET",
)

BASE_REQUIRED_APIS = (
    "run.googleapis.com",
    "iap.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
)

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    required: bool = True


def _run_gcloud(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["gcloud", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _gemini_enabled() -> bool | None:
    value = os.getenv("ENABLE_GEMINI", "false").strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return None


def _required_apis() -> tuple[str, ...]:
    apis = list(BASE_REQUIRED_APIS)
    if _gemini_enabled() is True:
        apis.append("aiplatform.googleapis.com")
    return tuple(apis)


def _env_checks() -> list[Check]:
    checks: list[Check] = []
    for name in REQUIRED_ENV:
        value = os.getenv(name, "").strip()
        checks.append(
            Check(
                f"env:{name}",
                "ok" if value else "missing",
                "configured" if value else "required deployment variable is not set",
            )
        )

    gemini_enabled = _gemini_enabled()
    checks.append(
        Check(
            "enable_gemini_format",
            "ok" if gemini_enabled is not None else "failed",
            (
                f"Gemini advisory mode {'enabled' if gemini_enabled else 'disabled'}"
                if gemini_enabled is not None
                else "ENABLE_GEMINI must be one of true/false, 1/0, yes/no, or on/off"
            ),
        )
    )

    project_number = os.getenv("PROJECT_NUMBER", "").strip()
    if project_number:
        checks.append(
            Check(
                "project_number_format",
                "ok" if project_number.isdigit() else "failed",
                "numeric project number" if project_number.isdigit() else "PROJECT_NUMBER must contain digits only",
            )
        )

    grafana_url = os.getenv("GRAFANA_URL", "").strip()
    if grafana_url:
        ok = bool(re.match(r"^https?://[^\s,]+$", grafana_url))
        checks.append(
            Check(
                "grafana_url_format",
                "ok" if ok else "failed",
                "absolute http(s) URL" if ok else "GRAFANA_URL must be an absolute http(s) URL without commas",
            )
        )

    service_account = os.getenv("RUNTIME_SERVICE_ACCOUNT", "").strip()
    if service_account:
        ok = bool(re.match(r"^[^@\s]+@[^@\s]+\.iam\.gserviceaccount\.com$", service_account))
        checks.append(
            Check(
                "runtime_service_account_format",
                "ok" if ok else "failed",
                "service-account email format" if ok else "RUNTIME_SERVICE_ACCOUNT must be a service-account email",
            )
        )

    image_url = os.getenv("IMAGE_URL", "").strip()
    if image_url:
        leaf = image_url.rsplit("/", 1)[-1]
        ok = ".pkg.dev/" in image_url and (":" in leaf or "@sha256:" in image_url)
        checks.append(
            Check(
                "image_url_format",
                "ok" if ok else "warning",
                "Artifact Registry image reference" if ok else "IMAGE_URL does not look like a pinned/tagged Artifact Registry image",
                required=False,
            )
        )
    return checks


def _gcloud_checks() -> list[Check]:
    if not shutil.which("gcloud"):
        return [Check("gcloud", "missing", "Google Cloud CLI is not installed or not on PATH")]

    checks = [Check("gcloud", "ok", "Google Cloud CLI found")]

    code, stdout, _ = _run_gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if code != 0 or not stdout:
        checks.append(Check("gcloud_auth", "failed", "no active gcloud account; run gcloud auth login or use an authorized environment"))
        return checks
    checks.append(Check("gcloud_auth", "ok", f"active account: {stdout.splitlines()[0]}"))

    project_id = os.getenv("PROJECT_ID", "").strip()
    if not project_id:
        return checks

    code, stdout, _ = _run_gcloud(["projects", "describe", project_id, "--format=value(projectNumber)"])
    if code != 0 or not stdout:
        checks.append(Check("project_access", "failed", f"cannot describe project {project_id!r}"))
        return checks
    project_number = stdout.splitlines()[0].strip()
    checks.append(Check("project_access", "ok", f"project accessible; number {project_number}"))

    configured_number = os.getenv("PROJECT_NUMBER", "").strip()
    if configured_number:
        checks.append(
            Check(
                "project_number_match",
                "ok" if project_number == configured_number else "failed",
                "PROJECT_NUMBER matches project" if project_number == configured_number else "PROJECT_NUMBER does not match PROJECT_ID",
            )
        )

    code, enabled, _ = _run_gcloud([
        "services",
        "list",
        f"--project={project_id}",
        "--enabled",
        "--format=value(config.name)",
    ])
    enabled_set = set(enabled.splitlines()) if code == 0 else set()
    for api in _required_apis():
        checks.append(
            Check(
                f"api:{api}",
                "ok" if api in enabled_set else "failed",
                "enabled" if api in enabled_set else "required API is not enabled or could not be verified",
            )
        )

    sa = os.getenv("RUNTIME_SERVICE_ACCOUNT", "").strip()
    if sa:
        code, _, _ = _run_gcloud(["iam", "service-accounts", "describe", sa, f"--project={project_id}"])
        checks.append(Check("runtime_service_account", "ok" if code == 0 else "failed", "service account exists" if code == 0 else "service account not found or not accessible"))

    for env_name in (
        "TELEMETRY_SECRET",
        "METRIC_ACTIVATION_SECRET",
        "LOG_ACTIVATION_SECRET",
        "GRAFANA_TOKEN_SECRET",
    ):
        secret = os.getenv(env_name, "").strip()
        if not secret:
            continue
        code, _, _ = _run_gcloud(["secrets", "describe", secret, f"--project={project_id}"])
        checks.append(
            Check(
                f"secret:{env_name}",
                "ok" if code == 0 else "failed",
                "secret exists; payload not read" if code == 0 else "secret not found or not accessible",
            )
        )

    image = os.getenv("IMAGE_URL", "").strip()
    if image and ".pkg.dev/" in image:
        code, _, _ = _run_gcloud(["artifacts", "docker", "images", "describe", image, f"--project={project_id}"])
        checks.append(
            Check(
                "container_image",
                "ok" if code == 0 else "failed",
                "container image exists" if code == 0 else "container image not found or not accessible",
            )
        )

    return checks


def _next_steps(checks: list[Check], *, offline: bool) -> list[str]:
    failures = [check for check in checks if check.required and check.status in {"failed", "missing"}]
    if not failures:
        if offline:
            return ["Run: python scripts/gcp_deploy_doctor.py --json to verify live Google Cloud prerequisites before deployment."]
        return ["Run: bash scripts/deploy_cloud_run.sh"]
    names = {check.name for check in failures}
    steps: list[str] = []
    if any(name.startswith("env:") for name in names):
        steps.append("Set every required deployment environment variable documented in GOOGLE_CLOUD_DEPLOYMENT.md.")
    if "enable_gemini_format" in names:
        steps.append("Set ENABLE_GEMINI to true or false using the same accepted boolean forms as scripts/deploy_cloud_run.sh.")
    if "gcloud" in names:
        steps.append("Install the Google Cloud CLI and place gcloud on PATH.")
    if "gcloud_auth" in names:
        steps.append("Authenticate gcloud using an authorized operator or workload identity.")
    if any(name.startswith("api:") for name in names):
        steps.append("Enable only the missing required Google Cloud APIs in the target project; Vertex AI is required when ENABLE_GEMINI=true.")
    if any(name.startswith("secret:") for name in names):
        steps.append("Create or grant access to the missing Secret Manager secrets; do not place secret values in environment variables.")
    if "container_image" in names:
        steps.append("Build and push the StageGuard API image to Artifact Registry, then set IMAGE_URL to that image.")
    if "runtime_service_account" in names:
        steps.append("Create or correct the least-privilege Cloud Run runtime service account.")
    if "project_number_match" in names:
        steps.append("Correct PROJECT_NUMBER so it matches PROJECT_ID before configuring the IAP service-agent binding.")
    return steps or ["Resolve the failed checks above, then rerun this doctor."]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate StageGuard Google Cloud deployment prerequisites without mutating cloud resources.")
    parser.add_argument("--offline", action="store_true", help="validate environment syntax only; do not invoke gcloud")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    checks = _env_checks()
    if not args.offline:
        checks.extend(_gcloud_checks())

    hard_failures = [check for check in checks if check.required and check.status in {"failed", "missing"}]
    payload = {
        "ready_to_deploy": not hard_failures and not args.offline,
        "offline_checks_passed": not hard_failures,
        "offline": args.offline,
        "gemini_enabled": _gemini_enabled(),
        "required_apis": list(_required_apis()),
        "checks": [asdict(check) for check in checks],
        "next_steps": _next_steps(checks, offline=args.offline),
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("StageGuard Google Cloud deployment doctor")
        print("=========================================")
        for check in checks:
            marker = {"ok": "PASS", "warning": "WARN", "missing": "MISS", "failed": "FAIL"}[check.status]
            requirement = "required" if check.required else "advisory"
            print(f"[{marker}] {check.name} ({requirement}): {check.detail}")
        print("\nNext steps:")
        for index, step in enumerate(payload["next_steps"], 1):
            print(f"  {index}. {step}")

    return 0 if not hard_failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
