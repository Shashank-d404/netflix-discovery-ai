"""Unit and integration tests for Gemini NLP extraction and /api/recommend/natural."""

import json
import os
from unittest.mock import MagicMock, patch
import pytest

from app import create_app
from services.catalog_service import CatalogService
from services.gemini_service import GeminiService, ExtractionResult
from services.recommender import UserPreferences


@pytest.fixture
def catalog_service():
    return CatalogService()


@pytest.fixture
def gemini_service(catalog_service):
    return GeminiService(api_key=None, catalog_service=catalog_service)


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "GEMINI_API_KEY": ""})
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------
# 1. Missing API Key & Local Heuristic Fallback
# ---------------------------------------------------------

def test_missing_api_key_activates_fallback(gemini_service):
    assert gemini_service.is_available() is False
    result = gemini_service.extract_preferences("I want a dark sci-fi movie in English under two hours")

    assert result.fallback_used is True
    assert result.extraction_mode == "fallback_heuristic"
    assert "not configured" in result.fallback_reason

    prefs = result.preferences
    assert "Sci-Fi" in prefs.genres
    assert prefs.content_type == "Movie"
    assert prefs.language == "English"
    assert "Dark" in prefs.moods
    assert prefs.max_duration_minutes == 120


def test_empty_query_handling(gemini_service):
    result = gemini_service.extract_preferences("")
    assert result.fallback_used is True
    assert result.preferences.genres == []


def test_heuristic_extraction_various_queries(gemini_service):
    # Query 1: Series with mood in Hindi
    res1 = gemini_service.extract_with_local_heuristic(
        "Looking for a heartwarming comedy series in Hindi"
    )
    assert "Comedy" in res1.genres
    assert res1.content_type == "Series"
    assert res1.language == "Hindi"
    assert "Heartwarming" in res1.moods

    # Query 2: Quick duration animation
    res2 = gemini_service.extract_with_local_heuristic(
        "A quick animated film under 90 minutes"
    )
    assert "Animation" in res2.genres
    assert res2.content_type == "Movie"
    assert res2.max_duration_minutes == 90
    assert res2.duration_category == "quick"

    # Query 3: Spanish thriller
    res3 = gemini_service.extract_with_local_heuristic(
        "Suspenseful Spanish thriller show"
    )
    assert "Thriller" in res3.genres
    assert res3.language == "Spanish"
    assert "Suspenseful" in res3.moods
    assert res3.content_type == "Series"


# ---------------------------------------------------------
# 2. Mocked Gemini API Calls
# ---------------------------------------------------------

def test_mocked_valid_gemini_extraction(catalog_service):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "genres": ["Sci-Fi", "Thriller"],
        "language": "English",
        "content_type": "Movie",
        "moods": ["Dark"],
        "tags": ["space", "dystopian"],
        "max_duration_minutes": 110,
        "duration_category": "standard"
    })
    mock_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="fake-test-key", catalog_service=catalog_service)
    service._client = mock_client

    result = service.extract_preferences("A dark sci-fi thriller under 110 mins")

    assert result.fallback_used is False
    assert result.extraction_mode == "gemini"
    assert result.preferences.genres == ["Sci-Fi", "Thriller"]
    assert result.preferences.language == "English"
    assert result.preferences.content_type == "Movie"
    assert result.preferences.moods == ["Dark"]
    assert result.preferences.max_duration_minutes == 110


def test_gemini_malformed_json_triggers_fallback(catalog_service):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "{ not valid json at all }"
    mock_client.models.generate_content.return_value = mock_response

    service = GeminiService(api_key="fake-test-key", catalog_service=catalog_service)
    service._client = mock_client

    result = service.extract_preferences("A dark sci-fi thriller")

    assert result.fallback_used is True
    assert result.extraction_mode == "fallback_heuristic"
    assert "unavailable" in result.fallback_reason.lower() or "json" in result.fallback_reason.lower()
    # Still extracts correctly via fallback
    assert "Sci-Fi" in result.preferences.genres


def test_gemini_api_network_failure_triggers_fallback(catalog_service):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Connection timeout to Gemini endpoint")

    service = GeminiService(api_key="fake-test-key", catalog_service=catalog_service)
    service._client = mock_client

    result = service.extract_preferences("A dark sci-fi thriller")

    assert result.fallback_used is True
    assert result.extraction_mode == "fallback_heuristic"
    assert "Connection timeout" in result.fallback_reason
    assert "Sci-Fi" in result.preferences.genres


# ---------------------------------------------------------
# 3. Taxonomy Validation Constraints
# ---------------------------------------------------------

def test_taxonomy_validation_filters_unsupported_items(gemini_service):
    raw_from_model = {
        "genres": ["Sci-Fi", "NonExistentGenre123"],
        "moods": ["Dark", "InventedMood456"],
        "language": "Klingon",  # Not in catalog
        "content_type": "Movie",
        "max_duration_minutes": 105,
    }
    validated = gemini_service.validate_and_normalize_taxonomy(raw_from_model)

    assert "Sci-Fi" in validated.genres
    assert "NonExistentGenre123" not in validated.genres
    assert "Dark" in validated.moods
    assert "InventedMood456" not in validated.moods
    # Unsupported mood is moved to tags as a fallback signal
    assert "inventedmood456" in validated.tags
    # Unsupported language is set to None
    assert validated.language is None
    assert validated.content_type == "Movie"
    assert validated.max_duration_minutes == 105


# ---------------------------------------------------------
# 4. Natural Recommendation Endpoint (/api/recommend/natural)
# ---------------------------------------------------------

def test_natural_endpoint_fallback_flow(client):
    payload = {
        "query": "I want a dark sci-fi thriller in English under two hours",
        "top_n": 3,
    }
    response = client.post(
        "/api/recommend/natural",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()

    assert data["success"] is True
    assert data["query"] == payload["query"]
    assert data["fallback_used"] is True
    assert data["extraction_mode"] == "fallback_heuristic"

    # Extracted preferences check
    extracted = data["extracted_preferences"]
    assert "Sci-Fi" in extracted["genres"]
    assert extracted["language"] == "English"
    assert extracted["max_duration_minutes"] == 120

    # Recommendations check
    assert data["count"] == 3
    assert len(data["recommendations"]) == 3
    for rec in data["recommendations"]:
        assert "id" in rec
        assert "title" in rec
        assert "total_score" in rec
        assert "score_breakdown" in rec
        assert "match_reasons" in rec


def test_natural_endpoint_with_mocked_gemini(catalog_service):
    # Mock GeminiService that returns gemini extraction_mode
    mock_service = MagicMock()
    mock_service.extract_preferences.return_value = ExtractionResult(
        preferences=UserPreferences(
            genres=["Sci-Fi", "Thriller"],
            language="English",
            content_type="Movie",
            moods=["Dark"],
            max_duration_minutes=120,
        ),
        extraction_mode="gemini",
        fallback_used=False,
        fallback_reason=None,
    )

    app = create_app({"TESTING": True, "GEMINI_SERVICE": mock_service})
    with app.test_client() as test_client:
        response = test_client.post(
            "/api/recommend/natural",
            data=json.dumps({"query": "Dark sci-fi under 2 hours"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["extraction_mode"] == "gemini"
        assert data["fallback_used"] is False
        assert len(data["recommendations"]) > 0


def test_natural_endpoint_recommendations_only_from_catalog(client, catalog_service):
    all_catalog_ids = {item["id"] for item in catalog_service.get_all_entries()}
    response = client.post(
        "/api/recommend/natural",
        data=json.dumps({"query": "Feel-good comedy series in Hindi"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    for item in data["recommendations"]:
        assert item["id"] in all_catalog_ids


def test_natural_endpoint_validation_errors(client):
    # Missing payload
    res_empty = client.post("/api/recommend/natural")
    assert res_empty.status_code == 400
    assert res_empty.get_json()["error"]["code"] == "MISSING_PAYLOAD"

    # Empty query
    res_empty_q = client.post(
        "/api/recommend/natural",
        data=json.dumps({"query": "   "}),
        content_type="application/json",
    )
    assert res_empty_q.status_code == 400
    assert res_empty_q.get_json()["error"]["code"] == "EMPTY_QUERY"

    # Invalid top_n
    res_bad_n = client.post(
        "/api/recommend/natural",
        data=json.dumps({"query": "sci-fi", "top_n": 99}),
        content_type="application/json",
    )
    assert res_bad_n.status_code == 400
    assert res_bad_n.get_json()["error"]["code"] == "INVALID_PARAM"


def test_secrets_never_included_in_responses(client, monkeypatch):
    secret_value = "super-secret-token-xyz-987"
    monkeypatch.setenv("GEMINI_API_KEY", secret_value)

    res = client.post(
        "/api/recommend/natural",
        data=json.dumps({"query": "Dark drama"}),
        content_type="application/json",
    )
    res_text = res.get_data(as_text=True)
    assert secret_value not in res_text
    assert "api_key" not in res_text.lower()
