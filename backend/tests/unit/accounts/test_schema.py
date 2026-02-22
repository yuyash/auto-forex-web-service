"""Unit tests for accounts schema module."""

from apps.accounts.schema import JWTAuthenticationScheme


class TestJWTAuthenticationScheme:
    """Test JWTAuthenticationScheme OpenAPI extension."""

    def test_target_class(self):
        assert JWTAuthenticationScheme.target_class == "apps.accounts.auth.JWTAuthentication"

    def test_name(self):
        assert JWTAuthenticationScheme.name == "jwtAuth"

    def test_get_security_definition(self):
        from unittest.mock import MagicMock

        scheme = MagicMock(spec=JWTAuthenticationScheme)
        definition = JWTAuthenticationScheme.get_security_definition(scheme, auto_schema=None)
        assert definition["type"] == "http"
        assert definition["scheme"] == "bearer"
        assert definition["bearerFormat"] == "JWT"
