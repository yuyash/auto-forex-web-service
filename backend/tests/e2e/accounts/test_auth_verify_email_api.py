"""E2E tests for POST /api/accounts/auth/verify-email and resend-verification."""

import pytest


@pytest.mark.django_db
class TestAuthVerifyEmail:
    def test_verify_invalid_token(self, api_client):
        resp = api_client.post(
            "/api/accounts/auth/verify-email",
            {"token": "invalid-verification-token"},
            format="json",
        )
        assert resp.status_code in (400, 404)

    def test_resend_verification_unauthenticated(self, api_client):
        resp = api_client.post(
            "/api/accounts/auth/resend-verification",
            {"email": "nobody@example.com"},
            format="json",
        )
        # Should not leak whether email exists
        assert resp.status_code in (200, 400, 404)
