"""
Pytest configuration for backend tests.
"""

import os

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")
