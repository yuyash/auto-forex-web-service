"""Tests for backend/config/__init__.py – celery_app export."""

from __future__ import annotations


class TestConfigInit:
    def test_celery_app_importable(self):
        """celery_app should be importable from config package."""
        from config import celery_app  # noqa: F401

    def test_all_contains_celery_app(self):
        """__all__ should contain 'celery_app' when celery is installed."""
        import config

        assert "celery_app" in config.__all__

    def test_all_is_tuple(self):
        """__all__ should be a tuple."""
        import config

        assert isinstance(config.__all__, tuple)
