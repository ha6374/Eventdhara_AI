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
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/categories/tree")
        assert response.status_code == 200
        tree = response.json()
        assert isinstance(tree, list)
        assert len(tree) >= 4

def test_image_placeholder_and_file_fallback():
    # 1. Non-existent image returns 404
    resp = client.get("/api/v1/images/99999999/file")
    assert resp.status_code == 404

    # 2. Placeholder endpoint returns valid SVG
    resp_svg = client.get("/api/v1/images/99999999/placeholder")
    assert resp_svg.status_code == 200
    assert "image/svg+xml" in resp_svg.headers.get("content-type", "")
    assert "<svg" in resp_svg.text
