from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import gcp_identifiers as ids  # noqa: E402


class GcpIdentifierTests(unittest.TestCase):
    def test_project_id_documented_boundaries(self) -> None:
        self.assertTrue(ids.valid_project_id("a12345"))
        self.assertTrue(ids.valid_project_id("stageguard-prod-123"))
        self.assertTrue(ids.valid_project_id("a" + "1" * 29))
        self.assertFalse(ids.valid_project_id("a1234"))
        self.assertFalse(ids.valid_project_id("A12345"))
        self.assertFalse(ids.valid_project_id("1stageguard"))
        self.assertFalse(ids.valid_project_id("stageguard-"))
        self.assertFalse(ids.valid_project_id("a" + "1" * 30))

    def test_cloud_run_service_name_boundaries(self) -> None:
        self.assertTrue(ids.valid_service_name("a"))
        self.assertTrue(ids.valid_service_name("stageguard-prod"))
        self.assertTrue(ids.valid_service_name("a" + "1" * 48))
        self.assertFalse(ids.valid_service_name("StageGuard"))
        self.assertFalse(ids.valid_service_name("1stageguard"))
        self.assertFalse(ids.valid_service_name("stageguard-"))
        self.assertFalse(ids.valid_service_name("a" + "1" * 49))

    def test_region_shape_is_bounded_and_lowercase(self) -> None:
        for value in ("us-central1", "asia-south1", "northamerica-northeast2"):
            self.assertTrue(ids.valid_region(value), value)
        for value in ("global", "US-CENTRAL1", "us central1", "-us-central1", "us-central1-"):
            self.assertFalse(ids.valid_region(value), value)

    def test_artifact_registry_tag_and_digest_forms(self) -> None:
        tagged = "us-central1-docker.pkg.dev/stageguard-prod/stageguard/runtime:v1.2.3"
        digest = "us-central1-docker.pkg.dev/stageguard-prod/stageguard/runtime@sha256:" + "a" * 64
        self.assertTrue(ids.valid_artifact_registry_image(tagged))
        self.assertTrue(ids.valid_artifact_registry_image(digest))
        self.assertFalse(ids.image_is_digest_pinned(tagged))
        self.assertTrue(ids.image_is_digest_pinned(digest))
        self.assertEqual(ids.image_project(tagged), "stageguard-prod")

    def test_artifact_registry_rejects_unversioned_or_non_registry_images(self) -> None:
        invalid = (
            "us-central1-docker.pkg.dev/stageguard-prod/stageguard/runtime",
            "gcr.io/stageguard-prod/runtime:v1",
            "docker.io/library/python:3.13",
            "us-central1-docker.pkg.dev/STAGEGUARD/stageguard/runtime:v1",
            "us-central1-docker.pkg.dev/stageguard-prod/stageguard/runtime@sha256:abc",
        )
        for value in invalid:
            self.assertFalse(ids.valid_artifact_registry_image(value), value)


if __name__ == "__main__":
    unittest.main()
