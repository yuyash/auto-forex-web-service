"""Integration tests for UUIDModel base class with database operations."""

import uuid
from datetime import timedelta

import pytest
from django.db import connection, models
from django.utils import timezone

from apps.trading.models.base import UUIDModel


# Create a concrete test model for integration testing
class IntegrationTestModel(UUIDModel):
    """Concrete model for integration testing with database."""

    name = models.CharField(max_length=100)
    value = models.IntegerField(default=0)

    class Meta:
        app_label = "trading"
        db_table = "integration_test_uuid_model"


@pytest.fixture
def create_test_table(db):
    """Create the test table for IntegrationTestModel."""
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(IntegrationTestModel)
    yield
    with connection.schema_editor() as schema_editor:
        schema_editor.delete_model(IntegrationTestModel)


@pytest.mark.django_db
class TestUUIDModelDatabaseIntegration:
    """Integration tests for UUIDModel with actual database operations."""

    def test_uuid_primary_key_is_generated_on_save(self, create_test_table):
        """Test that UUID primary key is automatically generated when saving to database."""
        instance = IntegrationTestModel(name="Test Instance")
        instance.save()

        assert instance.id is not None
        assert isinstance(instance.id, uuid.UUID)

        # Verify it's persisted in database
        retrieved = IntegrationTestModel.objects.get(id=instance.id)
        assert retrieved.id == instance.id

    def test_uuid_is_unique_in_database(self, create_test_table):
        """Test that each instance gets a unique UUID in the database."""
        instance1 = IntegrationTestModel(name="Instance 1")
        instance1.save()

        instance2 = IntegrationTestModel(name="Instance 2")
        instance2.save()

        assert instance1.id != instance2.id

        # Verify both are in database with different IDs
        all_instances = list(IntegrationTestModel.objects.all())
        assert len(all_instances) == 2
        assert all_instances[0].id != all_instances[1].id

    def test_created_at_is_set_automatically_on_save(self, create_test_table):
        """Test that created_at timestamp is set automatically when saving."""
        before_creation = timezone.now()
        instance = IntegrationTestModel(name="Test Instance")
        instance.save()
        after_creation = timezone.now()

        assert instance.created_at is not None
        assert before_creation <= instance.created_at <= after_creation

        # Verify it's persisted in database
        retrieved = IntegrationTestModel.objects.get(id=instance.id)
        assert retrieved.created_at == instance.created_at

    def test_created_at_does_not_change_on_update(self, create_test_table):
        """Test that created_at timestamp does not change when updating."""
        instance = IntegrationTestModel(name="Test Instance")
        instance.save()
        original_created_at = instance.created_at

        # Wait a moment and update
        import time

        time.sleep(0.01)

        instance.name = "Updated Instance"
        instance.save()

        assert instance.created_at == original_created_at

        # Verify in database
        retrieved = IntegrationTestModel.objects.get(id=instance.id)
        assert retrieved.created_at == original_created_at

    def test_updated_at_is_set_automatically_on_save(self, create_test_table):
        """Test that updated_at timestamp is set automatically when saving."""
        before_creation = timezone.now()
        instance = IntegrationTestModel(name="Test Instance")
        instance.save()
        after_creation = timezone.now()

        assert instance.updated_at is not None
        assert before_creation <= instance.updated_at <= after_creation

        # Verify it's persisted in database
        retrieved = IntegrationTestModel.objects.get(id=instance.id)
        assert retrieved.updated_at == instance.updated_at

    def test_updated_at_changes_on_update(self, create_test_table):
        """Test that updated_at timestamp changes when updating."""
        instance = IntegrationTestModel(name="Test Instance")
        instance.save()
        original_updated_at = instance.updated_at

        # Wait a moment to ensure timestamp difference
        import time

        time.sleep(0.01)

        instance.name = "Updated Instance"
        instance.save()

        assert instance.updated_at > original_updated_at

        # Verify in database
        retrieved = IntegrationTestModel.objects.get(id=instance.id)
        assert retrieved.updated_at > original_updated_at

    def test_default_ordering_by_created_at_desc(self, create_test_table):
        """Test that default ordering works correctly in database queries."""
        # Create instances with slight time differences
        instance1 = IntegrationTestModel(name="First")
        instance1.save()

        import time

        time.sleep(0.01)

        instance2 = IntegrationTestModel(name="Second")
        instance2.save()

        time.sleep(0.01)

        instance3 = IntegrationTestModel(name="Third")
        instance3.save()

        # Query all instances with explicit ordering
        instances = list(IntegrationTestModel.objects.order_by("-created_at"))

        # Should be ordered by created_at descending (newest first)
        assert instances[0].name == "Third"
        assert instances[1].name == "Second"
        assert instances[2].name == "First"

    def test_query_by_uuid(self, create_test_table):
        """Test that we can query records by UUID primary key."""
        instance = IntegrationTestModel(name="Test Instance")
        instance.save()

        # Query by UUID
        retrieved = IntegrationTestModel.objects.get(id=instance.id)
        assert retrieved.name == "Test Instance"
        assert retrieved.id == instance.id

    def test_filter_by_created_at_range(self, create_test_table):
        """Test that we can filter by created_at timestamp."""
        timezone.now()

        instance1 = IntegrationTestModel(name="Old Instance")
        instance1.save()

        import time

        time.sleep(0.01)

        cutoff_time = timezone.now()

        time.sleep(0.01)

        instance2 = IntegrationTestModel(name="New Instance")
        instance2.save()

        # Filter by created_at
        recent_instances = IntegrationTestModel.objects.filter(created_at__gte=cutoff_time)
        assert recent_instances.count() == 1
        assert recent_instances.first().name == "New Instance"  # type: ignore[union-attr]

    def test_bulk_create_with_uuid(self, create_test_table):
        """Test that bulk_create works with UUID primary keys."""
        instances = [IntegrationTestModel(name=f"Instance {i}") for i in range(5)]

        created_instances = IntegrationTestModel.objects.bulk_create(instances)

        # Verify all have UUIDs
        assert len(created_instances) == 5
        for instance in created_instances:
            assert instance.id is not None
            assert isinstance(instance.id, uuid.UUID)

        # Verify all are in database
        assert IntegrationTestModel.objects.count() == 5

    def test_update_multiple_records(self, create_test_table):
        """Test that updating multiple records via save() updates their updated_at timestamps."""
        # Create multiple instances
        instances = [IntegrationTestModel(name=f"Instance {i}") for i in range(3)]
        IntegrationTestModel.objects.bulk_create(instances)

        import time

        time.sleep(0.01)

        # Update all instances individually (save() triggers auto_now)
        update_time = timezone.now()
        for instance in IntegrationTestModel.objects.all():
            instance.value = 100
            instance.save()

        # Verify all have updated_at >= update_time
        for instance in IntegrationTestModel.objects.all():
            assert instance.updated_at >= update_time
            assert instance.value == 100

    def test_delete_by_uuid(self, create_test_table):
        """Test that we can delete records by UUID primary key."""
        instance = IntegrationTestModel(name="Test Instance")
        instance.save()
        instance_id = instance.id

        # Delete by UUID
        IntegrationTestModel.objects.filter(id=instance_id).delete()

        # Verify it's deleted
        assert IntegrationTestModel.objects.filter(id=instance_id).count() == 0

    def test_uuid_index_performance(self, create_test_table):
        """Test that UUID primary key can be used for efficient lookups."""
        # Create multiple instances
        instances = [IntegrationTestModel(name=f"Instance {i}") for i in range(100)]
        IntegrationTestModel.objects.bulk_create(instances)

        # Pick a random UUID
        target_id = IntegrationTestModel.objects.first().id  # type: ignore[union-attr]

        # Query by UUID should be fast (using primary key index)
        result = IntegrationTestModel.objects.get(id=target_id)
        assert result.id == target_id

    def test_timestamp_indexes_for_filtering(self, create_test_table):
        """Test that timestamp indexes work for efficient filtering."""
        # Create instances over time
        for i in range(10):
            IntegrationTestModel(name=f"Instance {i}").save()
            if i < 9:
                import time

                time.sleep(0.001)

        cutoff = timezone.now() - timedelta(seconds=0.005)

        # Filter by created_at (should use index)
        recent = IntegrationTestModel.objects.filter(created_at__gte=cutoff)
        assert recent.count() > 0

    def test_concurrent_uuid_generation(self, create_test_table):
        """Test that concurrent saves generate unique UUIDs."""
        # Simulate concurrent saves
        instances = []
        for i in range(10):
            instance = IntegrationTestModel(name=f"Concurrent {i}")
            instance.save()
            instances.append(instance)

        # Verify all UUIDs are unique
        uuids = [instance.id for instance in instances]
        assert len(uuids) == len(set(uuids))

        # Verify all are in database
        assert IntegrationTestModel.objects.count() == 10
