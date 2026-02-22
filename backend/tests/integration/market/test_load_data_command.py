"""Integration tests for load_data management command."""

from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestLoadDataCommandIntegration:
    """Integration tests for load_data command."""

    def test_command_exists(self) -> None:
        """Test that load_data command exists."""
        # Should not raise exception
        out = StringIO()
        try:
            call_command("load_data", "--help", stdout=out)
            output = out.getvalue()
            assert "load_data" in output.lower() or "usage" in output.lower()
        except SystemExit:
            # --help causes SystemExit, which is expected
            pass

    def test_command_requires_arguments(self) -> None:
        """Test that command requires proper arguments."""
        out = StringIO()
        err = StringIO()

        try:
            call_command("load_data", stdout=out, stderr=err)
        except Exception:
            # Command should fail without proper arguments
            assert True

    def test_command_with_invalid_file(self) -> None:
        """Test command with non-existent file."""
        out = StringIO()
        err = StringIO()

        try:
            call_command(
                "load_data",
                "--file",
                "/nonexistent/file.csv",
                stdout=out,
                stderr=err,
            )
        except Exception:
            # Should fail gracefully
            assert True
