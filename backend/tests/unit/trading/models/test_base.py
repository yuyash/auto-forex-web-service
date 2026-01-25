"""Unit tests for trading base models."""

import uuid

from django.db import models

from apps.trading.models.base import UUIDModel


# Create a concrete test model for testing the abstract UUIDModel
class ConcreteTestModel(UUIDModel):
    """Concrete model for testing UUIDModel."""

    name = models.CharField(max_length=100)

    class Meta:
        app_label = "trading"


class TestUUIDModel:
    """Test UUIDModel abstract base class."""

    def test_uuid_field_configuration(self):
        """Test that UUID field is configured correctly."""
        field = ConcreteTestModel._meta.get_field("id")

        assert isinstance(field, models.UUIDField)
        assert field.primary_key is True
        assert field.default == uuid.uuid4
        assert field.editable is False
        assert "Unique identifier" in field.help_text

    def test_created_at_field_configuration(self):
        """Test that created_at field is configured correctly."""
        field = ConcreteTestModel._meta.get_field("created_at")

        assert isinstance(field, models.DateTimeField)
        assert field.auto_now_add is True
        assert hasattr(field, "db_index")
        assert field.db_index is True  # type: ignore[attr-defined]
        assert "created" in field.help_text.lower()

    def test_updated_at_field_configuration(self):
        """Test that updated_at field is configured correctly."""
        field = ConcreteTestModel._meta.get_field("updated_at")

        assert isinstance(field, models.DateTimeField)
        assert field.auto_now is True
        assert hasattr(field, "db_index")
        assert field.db_index is True  # type: ignore[attr-defined]
        assert "updated" in field.help_text.lower()

    def test_model_is_abstract(self):
        """Test that UUIDModel is an abstract model."""
        assert UUIDModel._meta.abstract is True

    def test_default_ordering_configuration(self):
        """Test that default ordering is configured correctly."""
        assert UUIDModel._meta.ordering == ["-created_at"]

    def test_uuid_generation_on_instantiation(self):
        """Test that UUID is generated when model is instantiated."""
        instance = ConcreteTestModel(name="Test")

        # UUID should be generated even before saving
        assert instance.id is not None
        assert isinstance(instance.id, uuid.UUID)

    def test_uuid_uniqueness(self):
        """Test that each instance gets a unique UUID."""
        instance1 = ConcreteTestModel(name="Instance 1")
        instance2 = ConcreteTestModel(name="Instance 2")

        assert instance1.id != instance2.id

    def test_model_has_all_required_fields(self):
        """Test that model has all required fields from UUIDModel."""
        field_names = [f.name for f in ConcreteTestModel._meta.get_fields()]

        assert "id" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names

    def test_concrete_model_inherits_from_uuid_model(self):
        """Test that concrete model properly inherits from UUIDModel."""
        assert issubclass(ConcreteTestModel, UUIDModel)

    def test_uuid_field_type(self):
        """Test that id field is UUIDField type."""
        instance = ConcreteTestModel(name="Test")
        assert isinstance(instance._meta.get_field("id"), models.UUIDField)

    def test_timestamp_field_types(self):
        """Test that timestamp fields are DateTimeField type."""
        assert isinstance(ConcreteTestModel._meta.get_field("created_at"), models.DateTimeField)
        assert isinstance(ConcreteTestModel._meta.get_field("updated_at"), models.DateTimeField)

    def test_meta_class_inheritance(self):
        """Test that Meta class properties are inherited correctly."""
        # The abstract model should have ordering set
        assert hasattr(UUIDModel._meta, "ordering")
        assert UUIDModel._meta.ordering == ["-created_at"]

        # The abstract flag should be set
        assert UUIDModel._meta.abstract is True

    def test_field_help_text_presence(self):
        """Test that all fields have appropriate help text."""
        id_field = ConcreteTestModel._meta.get_field("id")
        created_field = ConcreteTestModel._meta.get_field("created_at")
        updated_field = ConcreteTestModel._meta.get_field("updated_at")

        assert hasattr(id_field, "help_text")
        assert len(id_field.help_text) > 0  # type: ignore[attr-defined]

        assert hasattr(created_field, "help_text")
        assert len(created_field.help_text) > 0  # type: ignore[attr-defined]

        assert hasattr(updated_field, "help_text")
        assert len(updated_field.help_text) > 0  # type: ignore[attr-defined]

    def test_uuid_default_callable(self):
        """Test that UUID default is a callable (uuid.uuid4)."""
        field = ConcreteTestModel._meta.get_field("id")
        assert hasattr(field, "default")
        assert callable(field.default)  # type: ignore[attr-defined]
        assert field.default == uuid.uuid4  # type: ignore[attr-defined]
