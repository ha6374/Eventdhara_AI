from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "EventDhara" in data["service"]


def test_dashboard_overview():
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    assert "total_images" in data["stats"]
    assert "daily_volume" in data
    assert "category_distribution" in data


def test_category_endpoints():
    response = client.get("/api/v1/categories/tree")
    assert response.status_code == 200
    tree = response.json()
    assert isinstance(tree, list)
    assert len(tree) >= 4
