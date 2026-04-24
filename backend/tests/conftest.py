"""
Pytest configuration for backend tests.
"""

import os
import random

import pytest
from rest_framework.test import APIRequestFactory

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")


@pytest.fixture(scope="session", autouse=True)
def deterministic_test_seed() -> None:
    """Reduce flaky ordering/seed-dependent failures across CI retries."""
    random.seed(42)


@pytest.fixture(scope="session")
def api_request_factory() -> APIRequestFactory:
    """Shared DRF request factory fixture for unit/integration view tests."""
    return APIRequestFactory()
