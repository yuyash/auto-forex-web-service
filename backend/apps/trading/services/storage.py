"""External storage service for large task execution data.

This module provides functionality for storing and retrieving large execution data
that exceeds reasonable database size limits. It supports multiple storage backends
including local filesystem and S3.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from django.conf import settings


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def store(self, key: str, data: Any) -> str:
        """Store data and return a reference identifier.

        Args:
            key: Unique identifier for the data
            data: Data to store (will be JSON serialized)

        Returns:
            str: Reference identifier for retrieving the data
        """
        ...

    @abstractmethod
    def retrieve(self, reference: str) -> Any:
        """Retrieve data using a reference identifier.

        Args:
            reference: Reference identifier returned by store()

        Returns:
            Any: The retrieved data (JSON deserialized)

        Raises:
            FileNotFoundError: If the reference does not exist
        """
        ...

    @abstractmethod
    def delete(self, reference: str) -> bool:
        """Delete data using a reference identifier.

        Args:
            reference: Reference identifier returned by store()

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        ...


class FileSystemStorageBackend(StorageBackend):
    """File system storage backend for local development and testing."""

    def __init__(self, base_path: str | None = None) -> None:
        """Initialize filesystem storage backend.

        Args:
            base_path: Base directory for storing files. Defaults to MEDIA_ROOT/task_data
        """
        if base_path is None:
            base_path = os.path.join(settings.MEDIA_ROOT, "task_data")
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def store(self, key: str, data: Any) -> str:
        """Store data to filesystem and return file path reference.

        Args:
            key: Unique identifier for the data (typically task_id)
            data: Data to store (will be JSON serialized)

        Returns:
            str: File path reference in format "fs://<relative_path>"
        """
        # Create subdirectory based on date for organization
        date_dir = datetime.now().strftime("%Y/%m/%d")
        storage_dir = self.base_path / date_dir
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{key}_{timestamp}.json"
        file_path = storage_dir / filename

        # Write data as JSON
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        # Return reference as relative path from base_path
        relative_path = file_path.relative_to(self.base_path)
        return f"fs://{relative_path}"

    def retrieve(self, reference: str) -> Any:
        """Retrieve data from filesystem using reference.

        Args:
            reference: File path reference in format "fs://<relative_path>"

        Returns:
            Any: The retrieved data (JSON deserialized)

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If reference format is invalid
        """
        if not reference.startswith("fs://"):
            raise ValueError(f"Invalid filesystem reference: {reference}")

        # Extract relative path
        relative_path = reference[5:]  # Remove "fs://" prefix
        file_path = self.base_path / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read and parse JSON
        with open(file_path, "r") as f:
            return json.load(f)

    def delete(self, reference: str) -> bool:
        """Delete data from filesystem using reference.

        Args:
            reference: File path reference in format "fs://<relative_path>"

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            if not reference.startswith("fs://"):
                return False

            relative_path = reference[5:]
            file_path = self.base_path / relative_path

            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False


class ExternalStorageService:
    """Service for managing external storage of large task execution data.

    This service automatically detects when data exceeds size limits and stores
    it externally, maintaining a reference in the database.
    """

    # Size limit for inline storage (1MB)
    SIZE_LIMIT_BYTES = 1024 * 1024

    def __init__(self, backend: StorageBackend | None = None) -> None:
        """Initialize external storage service.

        Args:
            backend: Storage backend to use. Defaults to FileSystemStorageBackend
        """
        self.backend = backend or FileSystemStorageBackend()

    def should_store_externally(self, data: Any) -> bool:
        """Determine if data should be stored externally based on size.

        Args:
            data: Data to check (will be JSON serialized for size calculation)

        Returns:
            bool: True if data exceeds size limit, False otherwise
        """
        try:
            # Serialize to JSON to get accurate size
            json_str = json.dumps(data, default=str)
            size_bytes = len(json_str.encode("utf-8"))
            return size_bytes > self.SIZE_LIMIT_BYTES
        except Exception:
            # If we can't serialize, assume it's too large
            return True

    def store_if_needed(self, task_id: UUID, data: Any) -> tuple[Any, str | None]:
        """Store data externally if it exceeds size limits.

        Args:
            task_id: UUID of the task
            data: Data to potentially store externally

        Returns:
            tuple[Any, str | None]: (data_or_reference, external_reference)
                - If data is small: (original_data, None)
                - If data is large: (None, external_reference)
        """
        if data is None:
            return None, None

        if self.should_store_externally(data):
            # Store externally and return reference
            reference = self.backend.store(str(task_id), data)
            return None, reference
        else:
            # Store inline
            return data, None

    def retrieve_data(self, inline_data: Any, external_reference: str | None) -> Any:
        """Retrieve data from inline storage or external storage.

        Args:
            inline_data: Data stored inline in database
            external_reference: Reference to externally stored data

        Returns:
            Any: The retrieved data

        Raises:
            FileNotFoundError: If external reference is invalid
        """
        if external_reference:
            return self.backend.retrieve(external_reference)
        return inline_data

    def delete_external_data(self, external_reference: str | None) -> bool:
        """Delete externally stored data.

        Args:
            external_reference: Reference to externally stored data

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        if external_reference:
            return self.backend.delete(external_reference)
        return False
