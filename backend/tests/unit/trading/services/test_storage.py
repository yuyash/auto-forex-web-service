"""Tests for external storage service."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from apps.trading.services.storage import (
    ExternalStorageService,
    FileSystemStorageBackend,
)


class TestFileSystemStorageBackend:
    """Tests for FileSystemStorageBackend."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def backend(self, temp_dir):
        """Create a FileSystemStorageBackend instance."""
        return FileSystemStorageBackend(base_path=temp_dir)

    def test_store_and_retrieve(self, backend):
        """Test storing and retrieving data."""
        key = str(uuid4())
        data = {"test": "data", "number": 42, "nested": {"key": "value"}}

        # Store data
        reference = backend.store(key, data)

        # Verify reference format
        assert reference.startswith("fs://")

        # Retrieve data
        retrieved_data = backend.retrieve(reference)

        # Verify data matches
        assert retrieved_data == data

    def test_store_creates_date_directory(self, backend, temp_dir):
        """Test that store creates date-based directory structure."""
        key = str(uuid4())
        data = {"test": "data"}

        # Store data
        _ = backend.store(key, data)

        # Verify date directory was created
        base_path = Path(temp_dir)
        date_dirs = list(base_path.glob("*/*/*/*"))  # YYYY/MM/DD/file.json
        assert len(date_dirs) > 0

    def test_retrieve_invalid_reference(self, backend):
        """Test retrieving with invalid reference format."""
        with pytest.raises(ValueError, match="Invalid filesystem reference"):
            backend.retrieve("invalid://reference")

    def test_retrieve_nonexistent_file(self, backend):
        """Test retrieving nonexistent file."""
        reference = "fs://nonexistent/file.json"

        with pytest.raises(FileNotFoundError):
            backend.retrieve(reference)

    def test_delete(self, backend):
        """Test deleting stored data."""
        key = str(uuid4())
        data = {"test": "data"}

        # Store data
        reference = backend.store(key, data)

        # Delete data
        success = backend.delete(reference)
        assert success is True

        # Verify file is deleted
        with pytest.raises(FileNotFoundError):
            backend.retrieve(reference)

    def test_delete_nonexistent_file(self, backend):
        """Test deleting nonexistent file."""
        reference = "fs://nonexistent/file.json"

        success = backend.delete(reference)
        assert success is False

    def test_delete_invalid_reference(self, backend):
        """Test deleting with invalid reference."""
        success = backend.delete("invalid://reference")
        assert success is False


class TestExternalStorageService:
    """Tests for ExternalStorageService."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def service(self, temp_dir):
        """Create an ExternalStorageService instance."""
        backend = FileSystemStorageBackend(base_path=temp_dir)
        return ExternalStorageService(backend=backend)

    def test_should_store_externally_small_data(self, service):
        """Test that small data is not stored externally."""
        small_data = {"key": "value"}

        should_store = service.should_store_externally(small_data)
        assert should_store is False

    def test_should_store_externally_large_data(self, service):
        """Test that large data is stored externally."""
        # Create data larger than 1MB
        large_data = {"data": "x" * (1024 * 1024 + 1)}

        should_store = service.should_store_externally(large_data)
        assert should_store is True

    def test_store_if_needed_small_data(self, service):
        """Test storing small data inline."""
        task_id = uuid4()
        small_data = {"key": "value"}

        inline_data, external_ref = service.store_if_needed(task_id, small_data)

        # Small data should be stored inline
        assert inline_data == small_data
        assert external_ref is None

    def test_store_if_needed_large_data(self, service):
        """Test storing large data externally."""
        task_id = uuid4()
        # Create data larger than 1MB
        large_data = {"data": "x" * (1024 * 1024 + 1)}

        inline_data, external_ref = service.store_if_needed(task_id, large_data)

        # Large data should be stored externally
        assert inline_data is None
        assert external_ref is not None
        assert external_ref.startswith("fs://")

    def test_store_if_needed_none_data(self, service):
        """Test storing None data."""
        task_id = uuid4()

        inline_data, external_ref = service.store_if_needed(task_id, None)

        assert inline_data is None
        assert external_ref is None

    def test_retrieve_data_inline(self, service):
        """Test retrieving inline data."""
        inline_data = {"key": "value"}
        external_ref = None

        retrieved_data = service.retrieve_data(inline_data, external_ref)

        assert retrieved_data == inline_data

    def test_retrieve_data_external(self, service):
        """Test retrieving external data."""
        task_id = uuid4()
        # Create and store large data
        large_data = {"data": "x" * (1024 * 1024 + 1)}
        _, external_ref = service.store_if_needed(task_id, large_data)

        # Retrieve data
        retrieved_data = service.retrieve_data(None, external_ref)

        assert retrieved_data == large_data

    def test_retrieve_data_none(self, service):
        """Test retrieving None data."""
        retrieved_data = service.retrieve_data(None, None)

        assert retrieved_data is None

    def test_delete_external_data(self, service):
        """Test deleting external data."""
        task_id = uuid4()
        # Create and store large data
        large_data = {"data": "x" * (1024 * 1024 + 1)}
        _, external_ref = service.store_if_needed(task_id, large_data)

        # Delete data
        success = service.delete_external_data(external_ref)
        assert success is True

        # Verify data is deleted
        with pytest.raises(FileNotFoundError):
            service.retrieve_data(None, external_ref)

    def test_delete_external_data_none(self, service):
        """Test deleting None external reference."""
        success = service.delete_external_data(None)
        assert success is False
