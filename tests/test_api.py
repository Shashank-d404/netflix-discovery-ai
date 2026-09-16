"""Integration tests for Flask API endpoints."""

import json
import pytest
from app import create_app


@pytest.fixture
def client():
    """Create a Flask test client configured for testing."""
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------
# 1. Health & Root Endpoints
# ---------------------------------------------------------

def test_root_endpoint_serves_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.content_type
    html = response.get_data(as_text=True)
    assert "NETFLIX — The Discovery Problem" in html
    assert "AI-Powered Personalized Content Discovery" in html
    assert "/static/css/style.css" in html
    assert "/static/js/app.js" in html


def test_static_assets_delivered(client):
    res_css = client.get("/static/css/style.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.content_type
    assert "--bg-primary" in res_css.get_data(as_text=True)

    res_js = client.get("/static/js/app.js")
    assert res_js.status_code == 200
    assert "javascript" in res_js.content_type
    assert "DOMContentLoaded" in res_js.get_data(as_text=True)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["status"] == "healthy"
    assert data["catalog_items_count"] >= 30
    # Ensure no secrets leaked
    assert "api_key" not in str(data).lower()
    assert "secret" not in str(data).lower()


# ---------------------------------------------------------
# 2. Catalog Taxonomy & Items Endpoints
# ---------------------------------------------------------

def test_catalog_filters_endpoint(client):
    response = client.get("/api/catalog/filters")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    filters = data["filters"]
    assert "genres" in filters and len(filters["genres"]) > 0
    assert "languages" in filters and "English" in filters["languages"]
    assert "moods" in filters and len(filters["moods"]) > 0
    assert "content_types" in filters and set(filters["content_types"]) == {"Movie", "Series"}
    assert "duration_presets" in filters and len(filters["duration_presets"]) == 3


def test_catalog_items_endpoint(client):
    response = client.get("/api/catalog/items")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] >= 30
    assert len(data["items"]) == data["count"]


# ---------------------------------------------------------
# 3. Recommendations Endpoint (/api/recommend)
# ---------------------------------------------------------

def test_recommend_valid_preferences(client):
    payload = {
        "genres": ["Sci-Fi", "Thriller"],
        "language": "English",
        "content_type": "Movie",
        "moods": ["Dark"],
        "max_duration_minutes": 120,
        "top_n": 4,
    }
    response = client.post(
        "/api/recommend",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 4
    assert len(data["recommendations"]) == 4

    # Validate structure of each recommendation
    for item in data["recommendations"]:
        assert "id" in item
        assert "title" in item
        assert "total_score" in item
        assert "score_breakdown" in item
        assert "match_reasons" in item
        assert 0.0 <= item["total_score"] <= 100.0


def test_recommend_empty_body(client):
    """Empty request body should not fail; should return top default items."""
    response = client.post("/api/recommend")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 5
    assert len(data["recommendations"]) == 5


def test_recommend_top_n_boundary(client):
    # Test top_n = 1
    res1 = client.post(
        "/api/recommend",
        data=json.dumps({"top_n": 1}),
        content_type="application/json",
    )
    assert res1.status_code == 200
    assert len(res1.get_json()["recommendations"]) == 1

    # Test top_n = 10
    res10 = client.post(
        "/api/recommend",
        data=json.dumps({"top_n": 10}),
        content_type="application/json",
    )
    assert res10.status_code == 200
    assert len(res10.get_json()["recommendations"]) == 10


def test_recommend_invalid_top_n(client):
    # top_n > 20
    res_high = client.post(
        "/api/recommend",
        data=json.dumps({"top_n": 50}),
        content_type="application/json",
    )
    assert res_high.status_code == 400
    assert res_high.get_json()["error"]["code"] == "INVALID_PARAM"

    # top_n < 1
    res_low = client.post(
        "/api/recommend",
        data=json.dumps({"top_n": 0}),
        content_type="application/json",
    )
    assert res_low.status_code == 400
    assert res_low.get_json()["error"]["code"] == "INVALID_PARAM"

    # top_n non-integer
    res_str = client.post(
        "/api/recommend",
        data=json.dumps({"top_n": "ten"}),
        content_type="application/json",
    )
    assert res_str.status_code == 400


def test_recommend_invalid_duration(client):
    # Negative duration
    res_neg = client.post(
        "/api/recommend",
        data=json.dumps({"max_duration_minutes": -30}),
        content_type="application/json",
    )
    assert res_neg.status_code == 400
    assert res_neg.get_json()["error"]["code"] == "INVALID_PARAM"


def test_recommend_non_json_content_type(client):
    res = client.post(
        "/api/recommend",
        data="genres=Sci-Fi",
        content_type="application/x-www-form-urlencoded",
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "INVALID_CONTENT_TYPE"


def test_recommend_malformed_json(client):
    res = client.post(
        "/api/recommend",
        data="{ malformed: json }",
        content_type="application/json",
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "MALFORMED_JSON"


def test_input_sanitization_strips_html_tags(client):
    payload = {
        "genres": ["<script>alert('xss')</script>Sci-Fi", "Drama"],
        "language": "<b>English</b>",
        "moods": ["<img src=x onerror=alert(1)>Dark"],
    }
    response = client.post(
        "/api/recommend",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    applied = data["preferences_applied"]
    assert "<script>" not in applied["genres"]
    assert "Sci-Fi" in applied["genres"]
    assert applied["language"] == "English"
    assert "Dark" in applied["moods"]


# ---------------------------------------------------------
# 4. Standard HTTP Error Envelopes
# ---------------------------------------------------------

def test_404_not_found(client):
    res = client.get("/api/unknown-endpoint")
    assert res.status_code == 404
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"


def test_405_method_not_allowed(client):
    # GET on POST-only endpoint
    res = client.get("/api/recommend")
    assert res.status_code == 405
    data = res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "METHOD_NOT_ALLOWED"
