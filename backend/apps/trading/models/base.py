"""Base models for trading app with UUID support."""

import uuid
from typing import List

from django.db import models


class UUIDModel(models.Model):
    """Abstract base model with UUID primary key and timestamps.

    This model provides:
    - UUID primary key for better distribution and security
    - Automatic created_at timestamp
    - Automatic updated_at timestamp

    All models that need UUID primary keys should inherit from this class.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this record",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this record was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="Timestamp when this record was last updated",
    )

    class Meta:
        abstract = True
        ordering: List[str] = ["-created_at"]
