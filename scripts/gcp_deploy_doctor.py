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

from gcp_identifiers import (
    valid_artifact_registry_image,
    valid_project_id,
    valid_region,
    valid_service_name,
)


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
    "CHECKPOINT_BUCKET",
    "CHECKPOINT_HMAC_SECRET",
)

BASE_REQUIRED_APIS = (
    "run.googleapis.com",
    "iap.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "policytroubleshooter.googleapis.com",
    "storage.googleapis.com",
)

SECRET_ENV_NAMES = (
    "TELEMETRY_SECRET",
    "METRIC_ACTIVATION_SECRET",
    "LOG_ACTIVATION_SECRET",
    "GRAFANA_TOKEN_SECRET",
    "CHECKPOINT_HMAC_SECRET",
)

SECRET_ACCESS_PERMISSION = "secretmanager.versions.access"
LOGGING_RUNTIME_PERMISSIONS = (
    "logging.logEntries.create",
    "logging.logEntries.list",
)
STORAGE_RUNTIME_PERMISSIONS = (
    "storage.objects.get",
    "storage.objects.create",
    "storage.objects.delete",
)
VERTEX_PREDICT_PERMISSION = "aiplatform.endpoints.predict"
DEFAULT_GEMINI_LOCATION = "global"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_CHECKPOINT_OBJECT = "stageguard/incident-checkpoint.json"
GCLOUD_TIMEOUT_SECONDS = 30
GCLOUD_TIMEOUT_EXIT_CODE = 124
GCLOUD_EXECUTION_EXIT_CODE = 126
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}
_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_IPV4_LIKE_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_SECRET_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,255}$")


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    required: bool = True


def _run_gcloud(args: list[str]) -> tuple[int, str, str]:
    """Run one read-only gcloud probe and convert process failures into safe results."""
    try:
        proc = subprocess.run(
            ["gcloud", *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=GCLOUD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return GCLOUD_TIMEOUT_EXIT_CODE, "", "gcloud command timed out"
    except (OSError, UnicodeError):
        return GCLOUD_EXECUTION_EXIT_CODE, "", "gcloud command could not be executed"
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _process_failure_detail(code: int, operation: str) -> str | None:
    """Return a sanitized, operation-specific detail for internal runner failures only."""
    if code == GCLOUD_TIMEOUT_EXIT_CODE:
        return f"gcloud process timed out while {operation}"
    if code == GCLOUD_EXECUTION_EXIT_CODE:
        return f"gcloud process could not be executed while {operation}"
    return None


def _gemini_enabled() -> bool | None:
    value = os.getenv("ENABLE_GEMINI", "false").strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return None


def _gemini_location() -> str:
    return os.getenv("GOOGLE_CLOUD_LOCATION", DEFAULT_GEMINI_LOCATION).strip() or DEFAULT_GEMINI_LOCATION


def _gemini_model() -> str:
    return os.getenv("STAGEGUARD_GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def _checkpoint_object() -> str:
    return os.getenv("CHECKPOINT_OBJECT", DEFAULT_CHECKPOINT_OBJECT)


def _valid_checkpoint_bucket(bucket: str) -> bool:
    return bool(
        _BUCKET_RE.fullmatch(bucket)
        and not _IPV4_LIKE_RE.fullmatch(bucket)
        and ".." not in bucket
        and not bucket.startswith("goog")
        and "google" not in bucket
    )


def _valid_checkpoint_object(raw: str) -> bool:
    name = raw.strip()
    segments = name.split("/")
    return bool(
        name
        and name == raw
        and not name.startswith("/")
        and not name.endswith("/")
        and len(name.encode("utf-8")) <= 512
        and not any(segment in {"", ".", ".."} for segment in segments)
        and not any(ord(char) < 32 or ord(char) == 127 for char in name)
        and "," not in name
        and "\\" not in name
    )


def _safe_cli_mapping_value(value: str) -> bool:
    """Return whether a value is safe inside gcloud comma-delimited mappings."""
    return bool(value and "," not in value and not any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value))


def _required_apis() -> tuple[str, ...]:
    apis = list(BASE_REQUIRED_APIS)
    if _gemini_enabled() is True:
        apis.append("aiplatform.googleapis.com")
    return tuple(apis)


def _env_checks() -> list[Check]:
    checks: list[Check] = []
    for name in REQUIRED_ENV:
        value = os.getenv(name, "").strip()
        checks.append(Check(f"env:{name}", "ok" if value else "missing", "configured" if value else "required deployment variable is not set"))

    project_id = os.getenv("PROJECT_ID", "").strip()
    if project_id:
        ok = valid_project_id(project_id)
        checks.append(Check("project_id_format", "ok" if ok else "failed", "valid Google Cloud project ID" if ok else "PROJECT_ID must be 6-30 lowercase letters, digits, or hyphens, start with a letter, and not end with a hyphen"))

    region = os.getenv("REGION", "").strip()
    if region:
        ok = valid_region(region)
        checks.append(Check("region_format", "ok" if ok else "failed", f"bounded Google Cloud region/location identifier: {region}" if ok else "REGION must be a bounded lowercase Google Cloud region/location identifier"))

    service_name = os.getenv("SERVICE_NAME", "").strip()
    if service_name:
        ok = valid_service_name(service_name)
        checks.append(Check("service_name_format", "ok" if ok else "failed", "valid Cloud Run service name" if ok else "SERVICE_NAME must be 1-49 lowercase letters, digits, or hyphens, start with a letter, and not end with a hyphen"))

    image_url = os.getenv("IMAGE_URL", "").strip()
    if image_url:
        safe = _safe_cli_mapping_value(image_url)
        checks.append(Check("image_url_cli_safety", "ok" if safe else "failed", "image reference is safe for deployment command serialization" if safe else "IMAGE_URL must not contain commas, whitespace, or control characters"))
        if safe:
            ok = valid_artifact_registry_image(image_url)
            checks.append(Check("image_url_format", "ok" if ok else "failed", "tagged or sha256-pinned Artifact Registry image reference" if ok else "IMAGE_URL must be a tagged or sha256-pinned Artifact Registry Docker image URI"))

    gemini_enabled = _gemini_enabled()
    checks.append(Check(
        "enable_gemini_format",
        "ok" if gemini_enabled is not None else "failed",
        f"Gemini advisory mode {'enabled' if gemini_enabled else 'disabled'}" if gemini_enabled is not None else "ENABLE_GEMINI must be one of true/false, 1/0, yes/no, or on/off",
    ))
    if gemini_enabled is True:
        location = _gemini_location()
        model = _gemini_model()
        location_ok = bool(re.fullmatch(r"[a-z0-9-]+", location))
        model_ok = bool(re.fullmatch(r"[A-Za-z0-9._-]+", model))
        checks.append(Check("gemini_location_format", "ok" if location_ok else "failed", f"Vertex AI location: {location}" if location_ok else "GOOGLE_CLOUD_LOCATION must be a Vertex AI location identifier"))
        checks.append(Check("gemini_model_format", "ok" if model_ok else "failed", f"Gemini publisher model: {model}" if model_ok else "STAGEGUARD_GEMINI_MODEL must be a model identifier, not a resource path or URL"))

    project_number = os.getenv("PROJECT_NUMBER", "").strip()
    if project_number:
        checks.append(Check("project_number_format", "ok" if project_number.isdigit() else "failed", "numeric project number" if project_number.isdigit() else "PROJECT_NUMBER must contain digits only"))

    grafana_url = os.getenv("GRAFANA_URL", "").strip()
    if grafana_url:
        ok = bool(re.fullmatch(r"https?://[^\s,]+", grafana_url))
        checks.append(Check("grafana_url_format", "ok" if ok else "failed", "absolute http(s) URL" if ok else "GRAFANA_URL must be an absolute http(s) URL without commas"))

    service_account = os.getenv("RUNTIME_SERVICE_ACCOUNT", "").strip()
    if service_account:
        ok = bool(re.fullmatch(r"[^@\s,]+@[^@\s,]+\.iam\.gserviceaccount\.com", service_account))
        checks.append(Check("runtime_service_account_format", "ok" if ok else "failed", "service-account email format" if ok else "RUNTIME_SERVICE_ACCOUNT must be a service-account email without commas"))

    iap_audience = os.getenv("IAP_AUDIENCE", "")
    if iap_audience:
        ok = _safe_cli_mapping_value(iap_audience)
        checks.append(Check("iap_audience_format", "ok" if ok else "failed", "safe IAP audience value" if ok else "IAP_AUDIENCE must not contain commas, whitespace, or control characters"))

    for name in SECRET_ENV_NAMES:
        secret_id = os.getenv(name, "").strip()
        if secret_id:
            ok = bool(_SECRET_ID_RE.fullmatch(secret_id))
            checks.append(Check(f"secret_id_format:{name}", "ok" if ok else "failed", "bounded Secret Manager secret ID" if ok else f"{name} must contain only letters, digits, underscores, or hyphens and be at most 255 characters"))

    bucket = os.getenv("CHECKPOINT_BUCKET", "").strip()
    if bucket:
        ok = _valid_checkpoint_bucket(bucket)
        checks.append(Check("checkpoint_bucket_format", "ok" if ok else "failed", f"bounded GCS bucket: {bucket}" if ok else "CHECKPOINT_BUCKET is not a valid bounded GCS bucket name"))

    checkpoint_object = _checkpoint_object()
    object_ok = _valid_checkpoint_object(checkpoint_object)
    checks.append(Check("checkpoint_object_format", "ok" if object_ok else "failed", f"bounded checkpoint object: {checkpoint_object}" if object_ok else "CHECKPOINT_OBJECT is not a valid bounded object path"))
    return checks


def _troubleshoot_permission(full_resource_name: str, service_account: str, permission: str, check_name: str, success_detail: str, denied_detail: str, unknown_detail: str) -> Check:
    """Evaluate one effective IAM permission with Policy Troubleshooter, fail closed."""
    code, stdout, _ = _run_gcloud([
        "policy-intelligence", "troubleshoot-policy", "iam", full_resource_name,
        f"--principal-email={service_account}", f"--permission={permission}", "--format=json",
    ])
    if code != 0:
        detail = _process_failure_detail(code, "checking effective IAM access")
        return Check(check_name, "failed", detail or "effective runtime access could not be verified with IAM Policy Troubleshooter")
    if not stdout:
        return Check(check_name, "failed", "effective runtime access could not be verified with IAM Policy Troubleshooter")
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return Check(check_name, "failed", "IAM Policy Troubleshooter returned an unreadable response")
    state = result.get("overallAccessState")
    if state == "CAN_ACCESS":
        return Check(check_name, "ok", success_detail)
    if state == "CANNOT_ACCESS":
        return Check(check_name, "failed", denied_detail)
    return Check(check_name, "failed", unknown_detail)


def _secret_access_check(project_number: str, service_account: str, secret: str, env_name: str) -> Check:
    full_resource_name = f"//secretmanager.googleapis.com/projects/{project_number}/secrets/{secret}"
    return _troubleshoot_permission(full_resource_name, service_account, SECRET_ACCESS_PERMISSION, f"secret_access:{env_name}", f"runtime service account has effective {SECRET_ACCESS_PERMISSION}; payload not read", f"runtime service account lacks effective {SECRET_ACCESS_PERMISSION}", "IAM Policy Troubleshooter could not determine effective runtime secret access")


def _logging_access_check(project_id: str, service_account: str, permission: str) -> Check:
    full_resource_name = f"//cloudresourcemanager.googleapis.com/projects/{project_id}"
    suffix = permission.rsplit(".", 1)[-1]
    return _troubleshoot_permission(full_resource_name, service_account, permission, f"logging_access:{suffix}", f"runtime service account has effective {permission} on the target project", f"runtime service account lacks effective {permission} on the target project", f"IAM Policy Troubleshooter could not determine effective {permission} access")


def _storage_access_check(bucket: str, object_name: str, service_account: str, permission: str) -> Check:
    """Verify the exact object permission used by the generation-based checkpoint store."""
    full_resource_name = f"//storage.googleapis.com/projects/_/buckets/{bucket}/objects/{object_name}"
    suffix = permission.rsplit(".", 1)[-1]
    return _troubleshoot_permission(full_resource_name, service_account, permission, f"checkpoint_storage_access:{suffix}", f"runtime service account has effective {permission} on the checkpoint object", f"runtime service account lacks effective {permission} on the checkpoint object", f"IAM Policy Troubleshooter could not determine effective {permission} access on the checkpoint object")


def _vertex_predict_access_check(project_id: str, service_account: str, location: str, model: str) -> Check:
    full_resource_name = f"//aiplatform.googleapis.com/projects/{project_id}/locations/{location}/publishers/google/models/{model}"
    return _troubleshoot_permission(full_resource_name, service_account, VERTEX_PREDICT_PERMISSION, "vertex_access:predict", f"runtime service account has effective {VERTEX_PREDICT_PERMISSION} on Gemini publisher model {model}", f"runtime service account lacks effective {VERTEX_PREDICT_PERMISSION} on Gemini publisher model {model}", f"IAM Policy Troubleshooter could not determine effective {VERTEX_PREDICT_PERMISSION} access")


def _cloud_run_region_check(project_id: str, region: str) -> Check:
    """Verify REGION against Cloud Run's live fully-managed region catalog."""
    code, stdout, _ = _run_gcloud([
        "run", "regions", "list",
        f"--project={project_id}",
        "--format=value(locationId)",
    ])
    if code != 0:
        detail = _process_failure_detail(code, "checking Cloud Run region availability")
        return Check("cloud_run_region_available", "failed", detail or "could not list currently available Cloud Run regions")
    regions = {line.strip() for line in stdout.splitlines() if line.strip()}
    if not regions:
        return Check("cloud_run_region_available", "failed", "Cloud Run region catalog returned no usable locations")
    if region in regions:
        return Check("cloud_run_region_available", "ok", f"Cloud Run currently reports {region} as available")
    return Check("cloud_run_region_available", "failed", f"Cloud Run does not currently report {region} as an available fully managed region")


def _gcloud_checks() -> list[Check]:
    if not shutil.which("gcloud"):
        return [Check("gcloud", "missing", "Google Cloud CLI is not installed or not on PATH")]
    checks = [Check("gcloud", "ok", "Google Cloud CLI found")]
    code, stdout, _ = _run_gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if code != 0:
        detail = _process_failure_detail(code, "checking active authentication")
        checks.append(Check("gcloud_auth", "failed", detail or "no active gcloud account; run gcloud auth login or use an authorized environment"))
        return checks
    if not stdout:
        checks.append(Check("gcloud_auth", "failed", "no active gcloud account; run gcloud auth login or use an authorized environment"))
        return checks
    checks.append(Check("gcloud_auth", "ok", f"active account: {stdout.splitlines()[0]}"))

    project_id = os.getenv("PROJECT_ID", "").strip()
    if not project_id:
        return checks
    code, stdout, _ = _run_gcloud(["projects", "describe", project_id, "--format=value(projectNumber)"])
    if code != 0:
        detail = _process_failure_detail(code, "checking project access")
        checks.append(Check("project_access", "failed", detail or f"cannot describe project {project_id!r}"))
        return checks
    if not stdout:
        checks.append(Check("project_access", "failed", f"cannot describe project {project_id!r}"))
        return checks
    project_number = stdout.splitlines()[0].strip()
    checks.append(Check("project_access", "ok", f"project accessible; number {project_number}"))

    configured_project_number = os.getenv("PROJECT_NUMBER", "").strip()
    checks.append(Check("project_number_match", "ok" if configured_project_number == project_number else "failed", "PROJECT_NUMBER matches project" if configured_project_number == project_number else f"PROJECT_NUMBER mismatch: expected {project_number}"))

    region = os.getenv("REGION", "").strip()
    if region:
        checks.append(_cloud_run_region_check(project_id, region))

    required_apis = _required_apis()
    code, stdout, _ = _run_gcloud(["services", "list", "--enabled", f"--project={project_id}", "--format=value(config.name)"])
    if code != 0:
        detail = _process_failure_detail(code, "checking enabled APIs")
        checks.append(Check("apis", "failed", detail or "could not list enabled APIs"))
    else:
        enabled = {line.strip() for line in stdout.splitlines() if line.strip()}
        missing = [api for api in required_apis if api not in enabled]
        checks.append(Check("apis", "ok" if not missing else "failed", "all required APIs enabled" if not missing else f"missing required APIs: {', '.join(missing)}"))

    for env_name in SECRET_ENV_NAMES:
        secret = os.getenv(env_name, "").strip()
        if not secret:
            continue
        code, _, _ = _run_gcloud(["secrets", "describe", secret, f"--project={project_id}", "--format=value(name)"])
        if code == 0:
            checks.append(Check(f"secret:{env_name}", "ok", "secret exists; payload not read"))
            checks.append(_secret_access_check(project_number, os.getenv("RUNTIME_SERVICE_ACCOUNT", "").strip(), secret, env_name))
        else:
            detail = _process_failure_detail(code, "checking Secret Manager resource existence")
            checks.append(Check(f"secret:{env_name}", "failed", detail or "secret not found or not accessible; payload not read"))

    bucket = os.getenv("CHECKPOINT_BUCKET", "").strip()
    if bucket:
        code, _, _ = _run_gcloud(["storage", "buckets", "describe", f"gs://{bucket}", f"--project={project_id}", "--format=value(name)"])
        if code == 0:
            checks.append(Check("checkpoint_bucket_exists", "ok", "checkpoint bucket exists"))
            checkpoint_object = _checkpoint_object()
            for permission in STORAGE_RUNTIME_PERMISSIONS:
                checks.append(_storage_access_check(bucket, checkpoint_object, os.getenv("RUNTIME_SERVICE_ACCOUNT", "").strip(), permission))
        else:
            detail = _process_failure_detail(code, "checking checkpoint bucket existence")
            checks.append(Check("checkpoint_bucket_exists", "failed", detail or "checkpoint bucket not found or not accessible"))

    service_account = os.getenv("RUNTIME_SERVICE_ACCOUNT", "").strip()
    for permission in LOGGING_RUNTIME_PERMISSIONS:
        checks.append(_logging_access_check(project_id, service_account, permission))

    if _gemini_enabled() is True:
        checks.append(_vertex_predict_access_check(project_id, service_account, _gemini_location(), _gemini_model()))

    image_url = os.getenv("IMAGE_URL", "").strip()
    if valid_artifact_registry_image(image_url):
        code, _, _ = _run_gcloud(["artifacts", "docker", "images", "describe", image_url, f"--project={project_id}", "--format=value(image_summary.digest)"])
        if code == 0:
            checks.append(Check("image_exists", "ok", "container image exists"))
        else:
            detail = _process_failure_detail(code, "checking Artifact Registry image existence")
            checks.append(Check("image_exists", "failed", detail or "container image not found or not accessible"))
    return checks


def _next_steps(checks: list[Check], offline: bool) -> list[str]:
    failed = {check.name for check in checks if check.required and check.status != "ok"}
    steps: list[str] = []
    if any(name.startswith("env:") for name in failed):
        steps.append("Set every required deployment environment variable; use Secret Manager secret names, never secret payloads.")
    if any(name in failed for name in ("project_id_format", "region_format", "service_name_format", "image_url_format")):
        steps.append("Fix PROJECT_ID, REGION, SERVICE_NAME, and IMAGE_URL so they satisfy the shared StageGuard Google Cloud identifier contract; Artifact Registry images must be explicitly tagged or sha256-pinned.")
    if "cloud_run_region_available" in failed:
        steps.append("Choose REGION from the live output of `gcloud run regions list`; do not rely on a static Cloud Run region list.")
    if "enable_gemini_format" in failed:
        steps.append("Set ENABLE_GEMINI to true/false (aliases 1/0, yes/no, on/off are accepted).")
    if any(name.startswith("secret_id_format:") for name in failed):
        steps.append("Use Secret Manager secret IDs containing only letters, digits, underscores, or hyphens (max 255 characters); never place payloads in secret-name variables.")
    if "iap_audience_format" in failed or "image_url_cli_safety" in failed or "grafana_url_format" in failed:
        steps.append("Remove commas, whitespace, and control characters from values serialized into Cloud Run deployment arguments.")
    if "checkpoint_bucket_format" in failed or "checkpoint_object_format" in failed:
        steps.append("Fix the checkpoint bucket/object identifiers so they match the bounded runtime contract before deploying.")
    if any(name.startswith("checkpoint_storage_access:") for name in failed):
        steps.append("Grant the runtime service account exactly storage.objects.get, storage.objects.create, and storage.objects.delete on the checkpoint object/bucket (roles/storage.objectUser is sufficient at bucket scope); storage.objects.list is not required.")
    if any(name.startswith("secret_access:") for name in failed):
        steps.append("Grant the runtime service account secretmanager.versions.access only on the StageGuard runtime secrets it needs.")
    if any(name.startswith("logging_access:") for name in failed):
        steps.append("Grant the runtime service account logging.logEntries.create and logging.logEntries.list on the target project using the narrowest suitable roles/custom role.")
    if "vertex_access:predict" in failed:
        steps.append("When Gemini is enabled, grant the runtime service account a role containing aiplatform.endpoints.predict for the configured publisher model/project.")
    if offline:
        steps.append("Run `python scripts/gcp_deploy_doctor.py --json` in the authorized deployment environment before deploying; offline validation can never report ready_to_deploy=true.")
    elif not failed:
        steps.append("Preflight passed. Review the target project/service values, then run scripts/deploy_cloud_run.sh from an authorized operator shell.")
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="validate local configuration only; never report deploy-ready")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    checks = _env_checks()
    if not args.offline and not any(check.required and check.status != "ok" for check in checks):
        checks.extend(_gcloud_checks())

    offline_checks_passed = not any(check.required and check.status != "ok" for check in _env_checks())
    ready_to_deploy = (not args.offline) and not any(check.required and check.status != "ok" for check in checks)
    payload = {
        "offline": args.offline,
        "offline_checks_passed": offline_checks_passed,
        "ready_to_deploy": ready_to_deploy,
        "gemini_enabled": _gemini_enabled(),
        "gemini_location": _gemini_location(),
        "gemini_model": _gemini_model(),
        "checkpoint_bucket": os.getenv("CHECKPOINT_BUCKET", "").strip(),
        "checkpoint_object": _checkpoint_object(),
        "required_apis": list(_required_apis()),
        "checks": [asdict(check) for check in checks],
        "next_steps": _next_steps(checks, args.offline),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for check in checks:
            print(f"[{check.status.upper():7}] {check.name}: {check.detail}")
        print(f"ready_to_deploy={str(ready_to_deploy).lower()}")
        for step in payload["next_steps"]:
            print(f"next: {step}")
    return 0 if (offline_checks_passed if args.offline else ready_to_deploy) else 2


if __name__ == "__main__":
    raise SystemExit(main())
