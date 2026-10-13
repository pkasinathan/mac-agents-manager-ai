"""Shared test fixtures for mac_agents_manager."""
import re

import pytest

from mac_agents_manager.app import app


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def csrf_token(client):
    """Extract the CSRF token from the index page."""
    resp = client.get("/")
    html = resp.data.decode()
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    assert match, "CSRF token meta tag not found in index page"
    return match.group(1)


@pytest.fixture
def mock_agents_dir(tmp_path, monkeypatch):
    """Redirect LaunchService.AGENTS_DIR to a temporary directory."""
    from mac_agents_manager.models import LaunchService
    monkeypatch.setattr(LaunchService, "AGENTS_DIR", tmp_path)
    return tmp_path
