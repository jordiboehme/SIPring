"""Tests for API endpoints."""

import json
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Set up test environment before importing app
os.environ["SIPRING_DATA_DIR"] = tempfile.mkdtemp()

from sipring.main import app
from sipring.storage import _storage, ConfigStorage


@pytest.fixture(autouse=True)
def reset_storage():
    """Reset storage before each test."""
    global _storage
    import sipring.storage as storage_module

    # Create fresh temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"configs": []}, f)
        temp_path = f.name

    storage_module._storage = ConfigStorage(file_path=temp_path)

    yield

    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


def test_health_check(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_list_configs_empty(client):
    """Test listing configs when empty."""
    response = client.get("/api/configs")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["configs"] == []


def test_create_config(client):
    """Test creating a configuration."""
    response = client.post("/api/configs", json={
        "name": "Test Doorbell",
        "sip_user": "1234",
        "sip_server": "10.0.0.1",
        "caller_name": "Doorbell",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Doorbell"
    assert data["slug"] == "test-doorbell"
    assert "ring_url" in data
    assert "cancel_url" in data


def test_get_config(client):
    """Test getting a configuration."""
    # Create first
    create_response = client.post("/api/configs", json={
        "name": "Test",
        "sip_user": "1234",
        "sip_server": "10.0.0.1",
        "caller_name": "Test",
    })
    config_id = create_response.json()["id"]

    # Get by UUID
    response = client.get(f"/api/configs/{config_id}")
    assert response.status_code == 200
    assert response.json()["id"] == config_id

    # Get by slug
    response = client.get("/api/configs/test")
    assert response.status_code == 200
    assert response.json()["id"] == config_id


def test_get_config_not_found(client):
    """Test getting non-existent config."""
    response = client.get("/api/configs/nonexistent")
    assert response.status_code == 404


def test_update_config(client):
    """Test updating a configuration."""
    # Create first
    create_response = client.post("/api/configs", json={
        "name": "Original",
        "sip_user": "1234",
        "sip_server": "10.0.0.1",
        "caller_name": "Test",
    })
    config_id = create_response.json()["id"]

    # Update
    response = client.put(f"/api/configs/{config_id}", json={
        "name": "Updated",
        "ring_duration": 60,
    })

    assert response.status_code == 200
    assert response.json()["name"] == "Updated"
    assert response.json()["ring_duration"] == 60


def test_delete_config(client):
    """Test deleting a configuration."""
    # Create first
    create_response = client.post("/api/configs", json={
        "name": "To Delete",
        "sip_user": "1234",
        "sip_server": "10.0.0.1",
        "caller_name": "Test",
    })
    config_id = create_response.json()["id"]

    # Delete
    response = client.delete(f"/api/configs/{config_id}")
    assert response.status_code == 204

    # Verify deleted
    response = client.get(f"/api/configs/{config_id}")
    assert response.status_code == 404


def test_ring_config_not_found(client):
    """Test triggering ring for non-existent config."""
    response = client.get("/ring/nonexistent")
    assert response.status_code == 404


def test_ring_disabled_config(client):
    """Test triggering ring for disabled config."""
    # Create disabled config
    create_response = client.post("/api/configs", json={
        "name": "Disabled",
        "sip_user": "1234",
        "sip_server": "10.0.0.1",
        "caller_name": "Test",
        "enabled": False,
    })
    config_id = create_response.json()["id"]

    # Try to ring
    response = client.get(f"/ring/{config_id}")
    assert response.status_code == 400
    assert "disabled" in response.json()["detail"].lower()


def test_dashboard(client):
    """Test dashboard page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "SIPring" in response.text


def test_new_config_form(client):
    """Test new config form page."""
    response = client.get("/config/new")
    assert response.status_code == 200
    assert "Create" in response.text
