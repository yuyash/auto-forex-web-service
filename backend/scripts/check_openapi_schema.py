"""Generate and update the checked-in OpenAPI schema when it changes."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import django
from django.core.management import call_command


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SCHEMA_PATH = REPO_ROOT / "docs" / "openapi.json"


def _generate_schema(target: Path) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    call_command(
        "spectacular",
        file=str(target),
        format="openapi-json",
        validate=True,
        fail_on_warn=True,
    )


def main() -> int:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        _generate_schema(tmp_path)
        generated = tmp_path.read_bytes() + b"\n"
        current = SCHEMA_PATH.read_bytes() if SCHEMA_PATH.exists() else b""
        if generated == current:
            return 0

        SCHEMA_PATH.write_bytes(generated)
        print(f"Updated {SCHEMA_PATH.relative_to(REPO_ROOT)}")
        return 0
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
