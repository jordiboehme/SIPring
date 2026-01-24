"""Tests for Pydantic models."""

import pytest
from uuid import UUID

from sipring.models import (
    RingConfigCreate,
    RingConfig,
    RingConfigUpdate,
    slugify,
)


def test_slugify():
    """Test slug generation."""
    assert slugify("Hello World") == "hello-world"
    assert slugify("Klingel (Haustür)") == "klingel-haustur"
    assert slugify("Test--Multiple---Dashes") == "test-multiple-dashes"
    assert slugify("  Leading Trailing  ") == "leading-trailing"


def test_ring_config_create_valid():
    """Test creating a valid config."""
    config = RingConfigCreate(
        name="Test Doorbell",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Doorbell",
    )
    assert config.name == "Test Doorbell"
    assert config.sip_port == 5060  # default
    assert config.ring_duration == 30  # default


def test_ring_config_create_with_slug():
    """Test config with custom slug."""
    config = RingConfigCreate(
        name="Test Doorbell",
        slug="my-doorbell",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Doorbell",
    )
    assert config.slug == "my-doorbell"


def test_ring_config_create_invalid_server():
    """Test invalid server format."""
    with pytest.raises(ValueError):
        RingConfigCreate(
            name="Test",
            sip_user="1234",
            sip_server="http://10.0.0.1",  # Should not be URL
            caller_name="Test",
        )


def test_ring_config_full():
    """Test full RingConfig with all fields."""
    config = RingConfig(
        name="Test",
        sip_user="1234",
        sip_server="10.0.0.1",
        caller_name="Test",
    )
    assert isinstance(config.id, UUID)
    assert config.created_at is not None
    assert config.last_ring_at is None
    assert config.last_ring_status is None


def test_ring_config_update_partial():
    """Test partial update model."""
    update = RingConfigUpdate(name="New Name")
    assert update.name == "New Name"
    assert update.sip_user is None

    # Exclude unset should only include name
    data = update.model_dump(exclude_unset=True)
    assert "name" in data
    assert "sip_user" not in data
