import unittest
from email.message import Message
from types import SimpleNamespace

from identity import (
    MAX_STATIC_BEARER_TOKEN_BYTES,
    MIN_STATIC_BEARER_TOKEN_BYTES,
    AuthenticationError,
    GoogleIapIdentityProvider,
    LocalDevelopmentIdentityProvider,
    StaticBearerIdentityProvider,
)


class IdentityProviderTests(unittest.TestCase):
    STATIC_TOKEN = "stageguard-test-token-0123456789abcdef"

    def handler(self, authorization=None, **headers_to_add):
        headers = Message()
        if authorization is not None:
            headers["Authorization"] = authorization
        for name, value in headers_to_add.items():
            headers[name.replace("_", "-")] = value
        return SimpleNamespace(headers=headers)

    def test_local_identity_is_process_configured_and_ignores_headers(self):
        provider = LocalDevelopmentIdentityProvider("trusted-local")
        identity = provider.authenticate(self.handler("Bearer attacker-controlled"))
        self.assertEqual("trusted-local", identity.subject)
        self.assertEqual("local-development", identity.provider)
        self.assertTrue(provider.is_development_only)

    def test_static_bearer_resolves_configured_subject(self):
        provider = StaticBearerIdentityProvider({self.STATIC_TOKEN: "operator@example.com"})
        identity = provider.authenticate(self.handler(f"Bearer {self.STATIC_TOKEN}"))
        self.assertEqual("operator@example.com", identity.subject)
        self.assertEqual("static-bearer", identity.provider)
        self.assertFalse(provider.is_development_only)

    def test_static_bearer_rejects_missing_or_invalid_credentials(self):
        provider = StaticBearerIdentityProvider({self.STATIC_TOKEN: "operator@example.com"})
        for authorization in (None, "Basic abc", "Bearer wrong"):
            with self.subTest(authorization=authorization):
                with self.assertRaises(AuthenticationError):
                    provider.authenticate(self.handler(authorization))

    def test_static_bearer_requires_strong_bounded_rfc6750_tokens(self):
        valid_minimum = "a" * MIN_STATIC_BEARER_TOKEN_BYTES
        provider = StaticBearerIdentityProvider({valid_minimum: "operator@example.com"})
        identity = provider.authenticate(self.handler(f"Bearer {valid_minimum}"))
        self.assertEqual("operator@example.com", identity.subject)

        invalid_tokens = (
            "a" * (MIN_STATIC_BEARER_TOKEN_BYTES - 1),
            "a" * (MAX_STATIC_BEARER_TOKEN_BYTES + 1),
            "a" * MIN_STATIC_BEARER_TOKEN_BYTES + " ",
            "a" * MIN_STATIC_BEARER_TOKEN_BYTES + "\n",
            "a" * MIN_STATIC_BEARER_TOKEN_BYTES + "?",
            "a" * MIN_STATIC_BEARER_TOKEN_BYTES + "=not-trailing",
        )
        for token in invalid_tokens:
            with self.subTest(token_length=len(token)):
                with self.assertRaises(ValueError):
                    StaticBearerIdentityProvider({token: "operator@example.com"})

    def test_static_bearer_bounds_untrusted_candidate_before_comparison(self):
        provider = StaticBearerIdentityProvider({self.STATIC_TOKEN: "operator@example.com"})
        oversized = "a" * (MAX_STATIC_BEARER_TOKEN_BYTES + 1)
        with self.assertRaisesRegex(AuthenticationError, "invalid bearer credential"):
            provider.authenticate(self.handler(f"Bearer {oversized}"))

    def test_empty_token_map_is_rejected(self):
        with self.assertRaises(ValueError):
            StaticBearerIdentityProvider({})

    def test_iap_identity_comes_only_from_verified_signed_assertion(self):
        audience = "/projects/123/locations/us-central1/services/stageguard"
        calls = []

        def verifier(assertion, expected_audience):
            calls.append((assertion, expected_audience))
            return {
                "iss": "https://cloud.google.com/iap",
                "aud": audience,
                "sub": "stable-user-123",
                "email": "operator@example.com",
            }

        provider = GoogleIapIdentityProvider(audience, verifier=verifier)
        identity = provider.authenticate(
            self.handler(
                X_Goog_IAP_JWT_Assertion="signed.jwt.value",
                X_Goog_Authenticated_User_Id="accounts.google.com:attacker",
                X_Goog_Authenticated_User_Email="accounts.google.com:attacker@example.com",
            )
        )
        self.assertEqual([("signed.jwt.value", audience)], calls)
        self.assertEqual("stable-user-123", identity.subject)
        self.assertEqual("google-iap", identity.provider)
        self.assertFalse(provider.is_development_only)

    def test_iap_rejects_unsigned_identity_headers(self):
        provider = GoogleIapIdentityProvider(
            "/projects/123/locations/us-central1/services/stageguard",
            verifier=lambda *_args: self.fail("verifier must not run without assertion"),
        )
        with self.assertRaises(AuthenticationError):
            provider.authenticate(
                self.handler(
                    X_Goog_Authenticated_User_Id="accounts.google.com:forged",
                    X_Goog_Authenticated_User_Email="accounts.google.com:forged@example.com",
                )
            )

    def test_iap_rejects_verification_failure_and_claim_drift(self):
        audience = "/projects/123/locations/us-central1/services/stageguard"

        def failing_verifier(*_args):
            raise ValueError("signature details must not escape")

        with self.assertRaisesRegex(AuthenticationError, "invalid IAP assertion"):
            GoogleIapIdentityProvider(audience, verifier=failing_verifier).authenticate(
                self.handler(X_Goog_IAP_JWT_Assertion="bad.jwt")
            )

        bad_claims = (
            {"iss": "attacker", "aud": audience, "sub": "user"},
            {"iss": "https://cloud.google.com/iap", "aud": "wrong", "sub": "user"},
            {"iss": "https://cloud.google.com/iap", "aud": audience, "sub": ""},
        )
        for claims in bad_claims:
            with self.subTest(claims=claims):
                provider = GoogleIapIdentityProvider(audience, verifier=lambda *_args, c=claims: c)
                with self.assertRaises(AuthenticationError):
                    provider.authenticate(self.handler(X_Goog_IAP_JWT_Assertion="signed.jwt"))

    def test_iap_requires_google_resource_audience_and_bounds_assertion(self):
        with self.assertRaises(ValueError):
            GoogleIapIdentityProvider("https://example.com/audience")

        provider = GoogleIapIdentityProvider(
            "/projects/123/locations/us-central1/services/stageguard",
            verifier=lambda *_args: self.fail("oversized assertion must fail before verifier"),
        )
        with self.assertRaises(AuthenticationError):
            provider.authenticate(self.handler(X_Goog_IAP_JWT_Assertion="x" * (16 * 1024 + 1)))


if __name__ == "__main__":
    unittest.main()
