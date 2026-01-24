"""Tests for JSON file storage."""

import json
import os
import tempfile
import pytest
from uuid import UUID

from sipring.storage import ConfigStorage, ConfigNotFoundError, StorageError
from sipring.models import RingConfigCreate, RingConfigUpdate


@pytest.fixture
def storage():
    """Create a temporary storage instance."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"configs": []}, f)
        temp_path = f.name

    yield ConfigStorage(file_path=temp_path)

    # Cleanup
    os.unlink(temp_path)


def test_create_config(storage):
    """Test creating a configuration."""
    config_data = RingConfigCreate(
        name="Test Doorbell",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Doorbell",
    )

    config = storage.create_config(config_data)

    assert config.name == "Test Doorbell"
    assert config.sip_user == "1234"
    assert isinstance(config.id, UUID)
    assert config.slug == "test-doorbell"


def test_list_configs(storage):
    """Test listing configurations."""
    # Create two configs
    storage.create_config(RingConfigCreate(
        name="Config 1",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Test 1",
    ))
    storage.create_config(RingConfigCreate(
        name="Config 2",
        sip_user="5678",
        sip_server="10.0.0.2",
        caller_name="Test 2",
    ))

    configs = storage.list_configs()
    assert len(configs) == 2


def test_get_config_by_uuid(storage):
    """Test getting config by UUID."""
    created = storage.create_config(RingConfigCreate(
        name="Test",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Test",
    ))

    found = storage.get_config(str(created.id))
    assert found.id == created.id


def test_get_config_by_slug(storage):
    """Test getting config by slug."""
    created = storage.create_config(RingConfigCreate(
        name="My Doorbell",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Test",
    ))

    found = storage.get_config("my-doorbell")
    assert found.id == created.id


def test_get_config_not_found(storage):
    """Test getting non-existent config."""
    with pytest.raises(ConfigNotFoundError):
        storage.get_config("nonexistent")


def test_update_config(storage):
    """Test updating a configuration."""
    created = storage.create_config(RingConfigCreate(
        name="Original Name",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Test",
    ))

    updated = storage.update_config(
        str(created.id),
        RingConfigUpdate(name="New Name", ring_duration=60)
    )

    assert updated.name == "New Name"
    assert updated.ring_duration == 60
    assert updated.sip_user == "1234"  # Unchanged


def test_delete_config(storage):
    """Test deleting a configuration."""
    created = storage.create_config(RingConfigCreate(
        name="To Delete",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Test",
    ))

    storage.delete_config(str(created.id))

    with pytest.raises(ConfigNotFoundError):
        storage.get_config(str(created.id))


def test_delete_config_not_found(storage):
    """Test deleting non-existent config."""
    with pytest.raises(ConfigNotFoundError):
        storage.delete_config("nonexistent")


def test_duplicate_slug_error(storage):
    """Test creating config with duplicate slug."""
    storage.create_config(RingConfigCreate(
        name="First",
        slug="my-slug",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Test",
    ))

    with pytest.raises(StorageError):
        storage.create_config(RingConfigCreate(
            name="Second",
            slug="my-slug",  # Duplicate
            sip_user="5678",
            sip_server="10.0.0.2",
            caller_name="Test 2",
        ))


def test_update_ring_status(storage):
    """Test updating ring status."""
    created = storage.create_config(RingConfigCreate(
        name="Test",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Test",
    ))

    storage.update_ring_status(str(created.id), "cancelled")

    found = storage.get_config(str(created.id))
    assert found.last_ring_status == "cancelled"
    assert found.last_ring_at is not None
