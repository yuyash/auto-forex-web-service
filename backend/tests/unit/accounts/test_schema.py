"""Unit tests for accounts OpenAPI schema extension."""

from apps.accounts.openapi import JWTAuthenticationExtension


class TestJWTAuthenticationExtension:
    """Test JWTAuthenticationExtension OpenAPI extension."""

    def test_target_class(self):
        assert JWTAuthenticationExtension.target_class == "apps.accounts.auth.JWTAuthentication"

    def test_name(self):
        assert JWTAuthenticationExtension.name == "JWTAuth"

    def test_get_security_definition(self):
        from unittest.mock import MagicMock

        scheme = MagicMock(spec=JWTAuthenticationExtension)
        definition = JWTAuthenticationExtension.get_security_definition(scheme, auto_schema=None)
        assert definition["type"] == "http"
        assert definition["scheme"] == "bearer"
        assert definition["bearerFormat"] == "JWT"
