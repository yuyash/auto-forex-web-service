"""
OpenAPI schema extensions for drf-spectacular.

This module provides schema extensions for custom authentication classes.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    OpenAPI authentication extension for JWTAuthentication.

    This extension tells drf-spectacular how to document JWT authentication
    in the OpenAPI schema.
    """

    target_class = "apps.accounts.auth.JWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        """
        Return the security definition for JWT authentication.

        Args:
            auto_schema: The auto schema instance

        Returns:
            Dictionary containing the security scheme definition
        """
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
