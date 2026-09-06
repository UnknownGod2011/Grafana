import unittest
from email.message import Message
from types import SimpleNamespace

from identity import AuthenticationError, LocalDevelopmentIdentityProvider, StaticBearerIdentityProvider


class IdentityProviderTests(unittest.TestCase):
    def handler(self, authorization=None):
        headers = Message()
        if authorization is not None:
            headers["Authorization"] = authorization
        return SimpleNamespace(headers=headers)

    def test_local_identity_is_process_configured_and_ignores_headers(self):
        provider = LocalDevelopmentIdentityProvider("trusted-local")
        identity = provider.authenticate(self.handler("Bearer attacker-controlled"))
        self.assertEqual("trusted-local", identity.subject)
        self.assertEqual("local-development", identity.provider)
        self.assertTrue(provider.is_development_only)

    def test_static_bearer_resolves_configured_subject(self):
        provider = StaticBearerIdentityProvider({"secret-token": "operator@example.com"})
        identity = provider.authenticate(self.handler("Bearer secret-token"))
        self.assertEqual("operator@example.com", identity.subject)
        self.assertEqual("static-bearer", identity.provider)
        self.assertFalse(provider.is_development_only)

    def test_static_bearer_rejects_missing_or_invalid_credentials(self):
        provider = StaticBearerIdentityProvider({"secret-token": "operator@example.com"})
        for authorization in (None, "Basic abc", "Bearer wrong"):
            with self.subTest(authorization=authorization):
                with self.assertRaises(AuthenticationError):
                    provider.authenticate(self.handler(authorization))

    def test_empty_token_map_is_rejected(self):
        with self.assertRaises(ValueError):
            StaticBearerIdentityProvider({})


if __name__ == "__main__":
    unittest.main()
