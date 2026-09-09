# Gemini / Vertex AI acceptance smoke

StageGuard keeps Gemini optional and advisory. The deterministic incident report, exact evidence revision, human approval, remediation, and Grafana-based recovery verification remain authoritative even when Gemini is enabled.

Use `scripts/gemini_acceptance_smoke.py` only after the read-only deployment doctor passes in the target Google Cloud environment.

## 1. Validate without sending a model request

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="global"
export STAGEGUARD_GEMINI_MODEL="gemini-2.5-flash"

python scripts/gemini_acceptance_smoke.py --json
```

The default mode performs syntax/configuration validation only. It does not initialize the Google Gen AI SDK and sends zero model requests.

## 2. Run the read-only deployment gate

```bash
export ENABLE_GEMINI=true
python scripts/gcp_deploy_doctor.py --json
```

Do not proceed to a paid acceptance request unless the doctor reports the live Google Cloud prerequisites as ready. The doctor verifies the configured project, required APIs, runtime service account, Secret Manager access, Cloud Logging access, and the conditional Vertex `aiplatform.endpoints.predict` permission without invoking Gemini.

## 3. Execute exactly one state-isolated request

Application Default Credentials must already be configured for an authorized identity, and the optional `google-genai` dependency must be installed.

```bash
python scripts/gemini_acceptance_smoke.py --execute --json
```

The executable path:

- creates a Vertex AI Google Gen AI SDK client for the configured project/location;
- sends exactly one `generate_content` request to the configured model;
- sends no StageGuard incident, Grafana, PromQL, LogQL, secret, approval, remediation, or recovery data;
- requests a tiny locked JSON response with `temperature=0` and a small output-token bound;
- validates the response exactly;
- never changes StageGuard state or any Google Cloud resource.

A successful result includes:

```json
{
  "purpose": "stageguard-gemini-acceptance",
  "request_count": 1,
  "state_mutation": false,
  "status": "ok"
}
```

The `--execute` flag is intentionally explicit because this step performs a real model inference and can incur normal Vertex AI usage charges.

## Production boundary

Passing this smoke test proves only the configured identity can make a minimal Gemini `generateContent` call through Vertex AI. It does **not** prove incident correctness, approval safety, remediation success, or recovery. Those remain separate StageGuard invariants and are independently verified through deterministic policy plus Grafana evidence.

## References

Current implementation follows Google's official Google Gen AI SDK / Vertex AI patterns:

- https://googleapis.github.io/python-genai/
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/googlegenaisdk-textgen-with-multi-img
