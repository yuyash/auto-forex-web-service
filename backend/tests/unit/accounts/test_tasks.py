"""Unit tests for accounts.tasks module."""

from unittest.mock import patch

from django.db.models import Q
from django.utils import timezone

from apps.accounts.tasks import cleanup_expired_refresh_tokens, models_q_expired_or_revoked


class TestModelsQExpiredOrRevoked:
    """Tests for the Q-filter builder."""

    def test_returns_q_object(self):
        now = timezone.now()
        result = models_q_expired_or_revoked(now)
        assert isinstance(result, Q)

    def test_contains_expired_condition(self):
        now = timezone.now()
        q = models_q_expired_or_revoked(now)
        q_str = str(q)
        assert "expires_at__lt" in q_str

    def test_contains_revoked_condition(self):
        now = timezone.now()
        q = models_q_expired_or_revoked(now)
        q_str = str(q)
        assert "revoked_at" in q_str


class TestCleanupExpiredRefreshTokens:
    """Tests for the cleanup Celery task.

    The task uses a lazy import: ``from apps.accounts.models import RefreshToken``
    inside the function body, so we patch the *models* module attribute.
    """

    @patch("apps.accounts.models.RefreshToken")
    def test_deletes_expired_tokens(self, mock_model_cls):
        mock_qs = mock_model_cls.objects.filter.return_value
        mock_qs.delete.return_value = (5, {"accounts.RefreshToken": 5})

        result = cleanup_expired_refresh_tokens()

        assert result == 5
        mock_model_cls.objects.filter.assert_called_once()
        mock_qs.delete.assert_called_once()

    @patch("apps.accounts.models.RefreshToken")
    def test_returns_zero_when_nothing_to_delete(self, mock_model_cls):
        mock_qs = mock_model_cls.objects.filter.return_value
        mock_qs.delete.return_value = (0, {})

        result = cleanup_expired_refresh_tokens()

        assert result == 0
