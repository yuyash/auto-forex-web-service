#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys

# Import at top level - this is a standard Django pattern
from django.core.management import execute_from_command_line


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    # Django management commands are Python modules, so their canonical names can't contain '-'.
    # We support a single alias here for ergonomics.
    if len(sys.argv) > 1 and sys.argv[1] == "load-data":
        sys.argv[1] = "load_data"
    try:
        execute_from_command_line(sys.argv)
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc


if __name__ == "__main__":
    main()
