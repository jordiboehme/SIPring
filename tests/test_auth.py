"""Tests for basic auth on the API and web UI."""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SIPRING_DATA_DIR", tempfile.mkdtemp())

from sipring.config import get_settings
from sipring.main import app
import sipring.storage as storage_module
from sipring.storage import ConfigStorage


@pytest.fixture(autouse=True)
def reset_storage():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"configs": []}, f)
        temp_path = f.name
    storage_module._storage = ConfigStorage(file_path=temp_path)
    yield
    os.unlink(temp_path)


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("SIPRING_USERNAME", "admin")
    monkeypatch.setenv("SIPRING_PASSWORD", "s3cret")
    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()


def test_api_requires_auth_when_enabled(auth_client):
    assert auth_client.get("/api/configs").status_code == 401
    assert auth_client.get("/api/events").status_code == 401


def test_api_accepts_valid_credentials(auth_client):
    response = auth_client.get("/api/configs", auth=("admin", "s3cret"))
    assert response.status_code == 200


def test_api_rejects_wrong_credentials(auth_client):
    response = auth_client.get("/api/configs", auth=("admin", "wrong"))
    assert response.status_code == 401


def test_ring_endpoints_stay_open(auth_client):
    """/ring is intentionally unauthenticated for IoT trigger devices."""
    response = auth_client.get("/ring/nonexistent-slug")
    assert response.status_code == 404  # not 401


def test_health_stays_open(auth_client):
    assert auth_client.get("/health").status_code == 200


def test_web_ui_requires_auth(auth_client):
    assert auth_client.get("/").status_code == 401


def test_no_auth_configured_means_open(monkeypatch):
    monkeypatch.delenv("SIPRING_USERNAME", raising=False)
    monkeypatch.delenv("SIPRING_PASSWORD", raising=False)
    get_settings.cache_clear()
    client = TestClient(app)
    assert client.get("/api/configs").status_code == 200
    assert client.get("/").status_code == 200
    get_settings.cache_clear()
