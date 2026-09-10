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
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}
_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_IPV4_LIKE_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


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


def _gemini_location() -> str:
    return os.getenv("GOOGLE_CLOUD_LOCATION", DEFAULT_GEMINI_LOCATION).strip() or DEFAULT_GEMINI_LOCATION


def _gemini_model() -> str:
    return os.getenv("STAGEGUARD_GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def _checkpoint_object() -> str:
    raw = os.getenv("CHECKPOINT_OBJECT", DEFAULT_CHECKPOINT_OBJECT)
    return raw


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

    gemini_enabled = _gemini_enabled()
    checks.append(Check(
        "enable_gemini_format",
        "ok" if gemini_enabled is not None else "failed",
        f"Gemini advisory mode {'enabled' if gemini_enabled else 'disabled'}" if gemini_enabled is not None else "ENABLE_GEMINI must be one of true/false, 1/0, yes/no, or on/off",
    ))
    if gemini_enabled is True:
        location = _gemini_location()
        model = _gemini_model()
        location_ok = bool(re.match(r"^[a-z0-9-]+$", location))
        model_ok = bool(re.match(r"^[A-Za-z0-9._-]+$", model))
        checks.append(Check("gemini_location_format", "ok" if location_ok else "failed", f"Vertex AI location: {location}" if location_ok else "GOOGLE_CLOUD_LOCATION must be a Vertex AI location identifier"))
        checks.append(Check("gemini_model_format", "ok" if model_ok else "failed", f"Gemini publisher model: {model}" if model_ok else "STAGEGUARD_GEMINI_MODEL must be a model identifier, not a resource path or URL"))

    project_number = os.getenv("PROJECT_NUMBER", "").strip()
    if project_number:
        checks.append(Check("project_number_format", "ok" if project_number.isdigit() else "failed", "numeric project number" if project_number.isdigit() else "PROJECT_NUMBER must contain digits only"))

    grafana_url = os.getenv("GRAFANA_URL", "").strip()
    if grafana_url:
        ok = bool(re.match(r"^https?://[^\s,]+$", grafana_url))
        checks.append(Check("grafana_url_format", "ok" if ok else "failed", "absolute http(s) URL" if ok else "GRAFANA_URL must be an absolute http(s) URL without commas"))

    service_account = os.getenv("RUNTIME_SERVICE_ACCOUNT", "").strip()
    if service_account:
        ok = bool(re.match(r"^[^@\s]+@[^@\s]+\.iam\.gserviceaccount\.com$", service_account))
        checks.append(Check("runtime_service_account_format", "ok" if ok else "failed", "service-account email format" if ok else "RUNTIME_SERVICE_ACCOUNT must be a service-account email"))

    bucket = os.getenv("CHECKPOINT_BUCKET", "").strip()
    if bucket:
        ok = _valid_checkpoint_bucket(bucket)
        checks.append(Check("checkpoint_bucket_format", "ok" if ok else "failed", f"bounded GCS bucket: {bucket}" if ok else "CHECKPOINT_BUCKET is not a valid bounded GCS bucket name"))

    checkpoint_object = _checkpoint_object()
    object_ok = _valid_checkpoint_object(checkpoint_object)
    checks.append(Check("checkpoint_object_format", "ok" if object_ok else "failed", f"bounded checkpoint object: {checkpoint_object}" if object_ok else "CHECKPOINT_OBJECT is not a valid bounded object path"))

    image_url = os.getenv("IMAGE_URL", "").strip()
    if image_url:
        leaf = image_url.rsplit("/", 1)[-1]
        ok = ".pkg.dev/" in image_url and (":" in leaf or "@sha256:" in image_url)
        checks.append(Check("image_url_format", "ok" if ok else "warning", "Artifact Registry image reference" if ok else "IMAGE_URL does not look like a pinned/tagged Artifact Registry image", required=False))
    return checks


def _troubleshoot_permission(full_resource_name: str, service_account: str, permission: str, check_name: str, success_detail: str, denied_detail: str, unknown_detail: str) -> Check:
    """Evaluate one effective IAM permission with Policy Troubleshooter, fail closed."""
    code, stdout, _ = _run_gcloud([
        "policy-intelligence", "troubleshoot-policy", "iam", full_resource_name,
        f"--principal-email={service_account}", f"--permission={permission}", "--format=json",
    ])
    if code != 0 or not stdout:
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
        checks.append(Check("project_number_match", "ok" if project_number == configured_number else "failed", "PROJECT_NUMBER matches project" if project_number == configured_number else "PROJECT_NUMBER does not match PROJECT_ID"))

    code, enabled, _ = _run_gcloud(["services", "list", f"--project={project_id}", "--enabled", "--format=value(config.name)"])
    enabled_set = set(enabled.splitlines()) if code == 0 else set()
    for api in _required_apis():
        checks.append(Check(f"api:{api}", "ok" if api in enabled_set else "failed", "enabled" if api in enabled_set else "required API is not enabled or could not be verified"))

    sa = os.getenv("RUNTIME_SERVICE_ACCOUNT", "").strip()
    service_account_exists = False
    if sa:
        code, _, _ = _run_gcloud(["iam", "service-accounts", "describe", sa, f"--project={project_id}"])
        service_account_exists = code == 0
        checks.append(Check("runtime_service_account", "ok" if service_account_exists else "failed", "service account exists" if service_account_exists else "service account not found or not accessible"))

    existing_secrets: list[tuple[str, str]] = []
    for env_name in SECRET_ENV_NAMES:
        secret = os.getenv(env_name, "").strip()
        if not secret:
            continue
        code, _, _ = _run_gcloud(["secrets", "describe", secret, f"--project={project_id}"])
        secret_exists = code == 0
        checks.append(Check(f"secret:{env_name}", "ok" if secret_exists else "failed", "secret exists; payload not read" if secret_exists else "secret not found or not accessible"))
        if secret_exists:
            existing_secrets.append((env_name, secret))

    bucket = os.getenv("CHECKPOINT_BUCKET", "").strip()
    bucket_exists = False
    if bucket and _valid_checkpoint_bucket(bucket):
        code, _, _ = _run_gcloud(["storage", "buckets", "describe", f"gs://{bucket}", f"--project={project_id}", "--format=value(name)"])
        bucket_exists = code == 0
        checks.append(Check("checkpoint_bucket", "ok" if bucket_exists else "failed", "checkpoint bucket exists and metadata is accessible" if bucket_exists else "checkpoint bucket not found or metadata is not accessible"))

    if service_account_exists and project_number.isdigit():
        for env_name, secret in existing_secrets:
            checks.append(_secret_access_check(project_number, sa, secret, env_name))
        for permission in LOGGING_RUNTIME_PERMISSIONS:
            checks.append(_logging_access_check(project_id, sa, permission))
        if bucket_exists:
            object_name = _checkpoint_object()
            if _valid_checkpoint_object(object_name):
                for permission in STORAGE_RUNTIME_PERMISSIONS:
                    checks.append(_storage_access_check(bucket, object_name, sa, permission))
        if _gemini_enabled() is True:
            checks.append(_vertex_predict_access_check(project_id, sa, _gemini_location(), _gemini_model()))

    image = os.getenv("IMAGE_URL", "").strip()
    if image and ".pkg.dev/" in image:
        code, _, _ = _run_gcloud(["artifacts", "docker", "images", "describe", image, f"--project={project_id}"])
        checks.append(Check("container_image", "ok" if code == 0 else "failed", "container image exists" if code == 0 else "container image not found or not accessible"))
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
    if "gemini_location_format" in names or "gemini_model_format" in names:
        steps.append("Set GOOGLE_CLOUD_LOCATION and STAGEGUARD_GEMINI_MODEL to plain Vertex AI location/model identifiers; do not pass URLs or resource paths.")
    if "checkpoint_bucket_format" in names or "checkpoint_object_format" in names:
        steps.append("Set CHECKPOINT_BUCKET and optional CHECKPOINT_OBJECT to identifiers accepted by the Cloud Run entrypoint; do not use traversal segments, delimiters, backslashes, or reserved bucket names.")
    if "gcloud" in names:
        steps.append("Install the Google Cloud CLI and place gcloud on PATH.")
    if "gcloud_auth" in names:
        steps.append("Authenticate gcloud using an authorized operator or workload identity.")
    if any(name.startswith("api:") for name in names):
        steps.append("Enable only the missing required Google Cloud APIs in the target project; Storage and Policy Troubleshooter are required for durable checkpoint preflight, and Vertex AI is required when ENABLE_GEMINI=true.")
    if any(name.startswith("secret:") for name in names):
        steps.append("Create or grant metadata visibility to the missing Secret Manager secrets, including CHECKPOINT_HMAC_SECRET; do not place secret values in environment variables.")
    if any(name.startswith("secret_access:") for name in names):
        steps.append("Grant the runtime service account secretmanager.versions.access on each mounted secret (normally roles/secretmanager.secretAccessor at the secret or an appropriate parent), then rerun the doctor.")
    if "checkpoint_bucket" in names:
        steps.append("Create or correct CHECKPOINT_BUCKET and ensure the operator running the doctor can read its metadata; the doctor never reads checkpoint object payloads.")
    if any(name.startswith("checkpoint_storage_access:") for name in names):
        steps.append("Grant the runtime service account storage.objects.get, storage.objects.create, and storage.objects.delete on the checkpoint bucket/object scope (roles/storage.objectUser at the bucket is the standard predefined role), then rerun the doctor. List or bucket-admin permissions are not required by StageGuard runtime.")
    if any(name.startswith("logging_access:") for name in names):
        steps.append("Grant the runtime service account the minimum Cloud Logging permissions needed by StageGuard: logging.logEntries.create for audit writes and logging.logEntries.list for restart/reconciliation reads, then rerun the doctor.")
    if any(name.startswith("vertex_access:") for name in names):
        steps.append("When ENABLE_GEMINI=true, grant the runtime service account aiplatform.endpoints.predict for the configured Vertex AI publisher-model path (roles/aiplatform.user is the standard predefined role, but a narrower custom/inherited grant is acceptable), then rerun the doctor.")
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
        "gemini_location": _gemini_location(),
        "gemini_model": _gemini_model(),
        "checkpoint_bucket": os.getenv("CHECKPOINT_BUCKET", "").strip(),
        "checkpoint_object": _checkpoint_object(),
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
