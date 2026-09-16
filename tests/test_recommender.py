"""Unit tests for the deterministic recommendation engine and scoring algorithm."""

import pytest
from typing import Any, Dict, List

from services.catalog_service import CatalogService
from services.recommender import (
    RecommendationEngine,
    UserPreferences,
    score_genre,
    score_mood_and_tags,
    score_language,
    score_content_type,
    score_duration,
    score_rating,
    WEIGHT_GENRE,
    WEIGHT_MOOD,
    WEIGHT_LANGUAGE,
    WEIGHT_CONTENT_TYPE,
    WEIGHT_DURATION,
    WEIGHT_RATING,
)


# Mock item fixture for unit scoring tests
@pytest.fixture
def sample_movie() -> Dict[str, Any]:
    return {
        "id": "mov-sample",
        "title": "Quantum Echo",
        "type": "Movie",
        "release_year": 2022,
        "genres": ["Sci-Fi", "Thriller"],
        "language": "English",
        "moods": ["Dark", "Mind-bending"],
        "tags": ["time-travel", "quantum", "cyberpunk"],
        "duration_minutes": 105,
        "duration_display": "1h 45m",
        "rating": 8.0,
        "synopsis": "A physicist unravels temporal echoes.",
        "poster_gradient": "linear-gradient(135deg, #000, #333)",
        "featured_cast": ["Jane Doe"],
    }


# ---------------------------------------------------------
# 1. Exact, Partial & Disjoint Genre Matches
# ---------------------------------------------------------

def test_exact_genre_match():
    score, matched = score_genre(["Sci-Fi", "Thriller"], ["Sci-Fi", "Thriller", "Drama"])
    assert score == WEIGHT_GENRE  # 35.0 pts
    assert sorted(matched) == ["Sci-Fi", "Thriller"]


def test_partial_genre_match():
    # User requests 2 genres, movie only has 1
    score, matched = score_genre(["Sci-Fi", "Comedy"], ["Sci-Fi", "Action"])
    assert score == round(WEIGHT_GENRE * 0.5, 2)  # 17.5 pts
    assert matched == ["Sci-Fi"]


def test_zero_genre_match():
    score, matched = score_genre(["Horror", "Romance"], ["Sci-Fi", "Action"])
    assert score == 0.0
    assert matched == []


def test_genre_case_insensitivity():
    score, matched = score_genre(["sci-fi"], ["Sci-Fi", "Action"])
    assert score == WEIGHT_GENRE
    assert matched == ["Sci-Fi"]


# ---------------------------------------------------------
# 2. Mood and Tag Matches
# ---------------------------------------------------------

def test_mood_exact_match(sample_movie):
    score, matched_moods, matched_tags = score_mood_and_tags(
        user_moods=["Dark"],
        user_tags=[],
        item_moods=sample_movie["moods"],
        item_tags=sample_movie["tags"],
    )
    assert score == WEIGHT_MOOD  # 25.0 pts
    assert "Dark" in matched_moods


def test_tag_match_via_user_tags(sample_movie):
    score, matched_moods, matched_tags = score_mood_and_tags(
        user_moods=[],
        user_tags=["time-travel"],
        item_moods=sample_movie["moods"],
        item_tags=sample_movie["tags"],
    )
    assert score == WEIGHT_MOOD  # 25.0 pts
    assert "time-travel" in matched_tags


def test_partial_mood_and_tag_match(sample_movie):
    # User requests 2 targets, 1 matches
    score, matched_moods, matched_tags = score_mood_and_tags(
        user_moods=["Dark", "Feel-Good"],
        user_tags=[],
        item_moods=sample_movie["moods"],
        item_tags=sample_movie["tags"],
    )
    assert score == round(WEIGHT_MOOD * 0.5, 2)  # 12.5 pts
    assert matched_moods == ["Dark"]


# ---------------------------------------------------------
# 3. Language Matches
# ---------------------------------------------------------

def test_language_exact_match():
    score, matched = score_language("English", "English")
    assert score == WEIGHT_LANGUAGE  # 15.0
    assert matched is True


def test_language_mismatch():
    score, matched = score_language("Hindi", "English")
    assert score == 0.0
    assert matched is False


def test_language_any_or_empty():
    assert score_language("Any", "Spanish")[0] == WEIGHT_LANGUAGE
    assert score_language("", "Korean")[0] == WEIGHT_LANGUAGE
    assert score_language(None, "Japanese")[0] == WEIGHT_LANGUAGE


# ---------------------------------------------------------
# 4. Content Type Matches
# ---------------------------------------------------------

def test_content_type_exact_match():
    score, matched = score_content_type("Movie", "Movie")
    assert score == WEIGHT_CONTENT_TYPE  # 10.0
    assert matched is True

    score_s, matched_s = score_content_type("Series", "Series")
    assert score_s == WEIGHT_CONTENT_TYPE
    assert matched_s is True


def test_content_type_mismatch():
    score, matched = score_content_type("Series", "Movie")
    assert score == 0.0
    assert matched is False


def test_content_type_any_or_none():
    assert score_content_type("Any", "Movie")[0] == WEIGHT_CONTENT_TYPE
    assert score_content_type(None, "Series")[0] == WEIGHT_CONTENT_TYPE


# ---------------------------------------------------------
# 5. Duration Compatibility
# ---------------------------------------------------------

def test_duration_within_limit():
    # Movie is 105 mins, limit is 120 mins -> 10.0 pts
    score, comp = score_duration(max_duration_minutes=120, duration_category=None, item_duration_minutes=105)
    assert score == WEIGHT_DURATION
    assert comp is True


def test_duration_exceeding_limit():
    # Movie is 135 mins, limit is 120 mins (+15 min overage)
    # Penalty: (15 / 30) * 5 = 2.5 pts -> score 7.5
    score, comp = score_duration(max_duration_minutes=120, duration_category=None, item_duration_minutes=135)
    assert score == 7.5
    assert comp is True


def test_duration_severely_exceeding_limit():
    # Movie is 180 mins, limit is 120 mins (+60 min overage)
    # Penalty: (60 / 30) * 5 = 10 pts -> score 0.0
    score, comp = score_duration(max_duration_minutes=120, duration_category=None, item_duration_minutes=180)
    assert score == 0.0
    assert comp is False


def test_duration_category_quick():
    # Quick (<90 mins): item is 85 mins -> 10 pts
    score, _ = score_duration(max_duration_minutes=None, duration_category="quick", item_duration_minutes=85)
    assert score == WEIGHT_DURATION


# ---------------------------------------------------------
# 6. Rating Quality Boost
# ---------------------------------------------------------

def test_rating_boost_calculation():
    assert score_rating(10.0) == 5.0
    assert score_rating(8.0) == 4.0
    assert score_rating(5.0) == 2.5
    assert score_rating(0.0) == 0.0
    assert score_rating(None) == 0.0


# ---------------------------------------------------------
# 7. Missing Optional Preferences
# ---------------------------------------------------------

def test_missing_optional_preferences_no_penalty(sample_movie):
    """User provides no preferences: must not crash and should award neutral full credit."""
    engine = RecommendationEngine()
    empty_prefs = UserPreferences()
    scored = engine.score_item(sample_movie, empty_prefs)

    # Genre=35, Mood=25, Lang=15, Type=10, Duration=10, Rating=4.0 -> Total = 99.0
    assert scored["score_breakdown"]["genre_match"] == 35.0
    assert scored["score_breakdown"]["mood_match"] == 25.0
    assert scored["score_breakdown"]["language_match"] == 15.0
    assert scored["score_breakdown"]["content_type_match"] == 10.0
    assert scored["score_breakdown"]["duration_match"] == 10.0
    assert scored["score_breakdown"]["rating_boost"] == 4.0
    assert scored["total_score"] == 99.0


# ---------------------------------------------------------
# 8. Invalid Preferences Handling
# ---------------------------------------------------------

def test_invalid_preference_types():
    raw_bad_data = {
        "genres": 12345,  # Non-list
        "language": None,
        "content_type": ["not", "a", "string"],
        "moods": None,
        "max_duration_minutes": "not-a-number",
        "random_extra_key": True,
    }
    prefs = UserPreferences.from_dict(raw_bad_data)
    assert isinstance(prefs.genres, list)
    assert prefs.genres == []
    assert prefs.max_duration_minutes is None


def test_negative_duration():
    prefs = UserPreferences.from_dict({"max_duration_minutes": -50})
    assert prefs.max_duration_minutes is None


# ---------------------------------------------------------
# 9. Score Boundaries & Determinism
# ---------------------------------------------------------

def test_score_boundaries(sample_movie):
    engine = RecommendationEngine()
    prefs = UserPreferences(
        genres=["Sci-Fi"],
        language="English",
        content_type="Movie",
        moods=["Dark"],
        max_duration_minutes=120,
    )
    scored = engine.score_item(sample_movie, prefs)
    assert 0.0 <= scored["total_score"] <= 100.0


def test_deterministic_ordering():
    """Verify stable ordering when scores or ratings are identical."""
    items = [
        {
            "id": "mov-b",
            "title": "Beta Movie",
            "type": "Movie",
            "release_year": 2020,
            "genres": ["Action"],
            "language": "English",
            "moods": ["Dark"],
            "tags": [],
            "duration_minutes": 100,
            "duration_display": "1h 40m",
            "rating": 8.0,
            "synopsis": "Synopsis B",
            "poster_gradient": "none",
            "featured_cast": []
        },
        {
            "id": "mov-a",
            "title": "Alpha Movie",
            "type": "Movie",
            "release_year": 2020,
            "genres": ["Action"],
            "language": "English",
            "moods": ["Dark"],
            "tags": [],
            "duration_minutes": 100,
            "duration_display": "1h 40m",
            "rating": 8.0,
            "synopsis": "Synopsis A",
            "poster_gradient": "none",
            "featured_cast": []
        }
    ]
    # Both movies have identical scores and release year; Alpha should precede Beta alphabetically
    class MockService:
        def get_all_entries(self):
            return items

    engine = RecommendationEngine(catalog_service=MockService())
    results = engine.recommend(UserPreferences(genres=["Action"]), top_n=2)
    assert results[0]["title"] == "Alpha Movie"
    assert results[1]["title"] == "Beta Movie"


# ---------------------------------------------------------
# 10. Zero Hallucination: Recommendations Only from Catalog
# ---------------------------------------------------------

def test_recommendations_only_from_catalog():
    catalog_service = CatalogService()
    engine = RecommendationEngine(catalog_service=catalog_service)
    all_catalog_ids = {item["id"] for item in catalog_service.get_all_entries()}

    recommendations = engine.recommend(
        UserPreferences(genres=["Sci-Fi"], language="English"), top_n=10
    )
    assert len(recommendations) > 0
    for rec in recommendations:
        assert rec["id"] in all_catalog_ids
        assert "score_breakdown" in rec
        assert "match_reasons" in rec


# ---------------------------------------------------------
# 11. Empty Catalog Handling
# ---------------------------------------------------------

def test_empty_catalog_returns_empty_list():
    class EmptyService:
        def get_all_entries(self):
            return []

    engine = RecommendationEngine(catalog_service=EmptyService())
    results = engine.recommend(UserPreferences(genres=["Drama"]), top_n=5)
    assert results == []


# ---------------------------------------------------------
# 12. User Scenario: "Dark sci-fi thriller in English under 2 hours"
# ---------------------------------------------------------

def test_user_scenario_dark_scifi_thriller():
    """Validates the core problem statement example."""
    engine = RecommendationEngine()
    prefs = UserPreferences(
        genres=["Sci-Fi", "Thriller"],
        language="English",
        content_type="Movie",
        moods=["Dark"],
        max_duration_minutes=120,
    )
    results = engine.recommend(prefs, top_n=5)
    assert len(results) > 0

    top_title = results[0]["title"]
    # Ex Machina (108m, Sci-Fi, Dark, English) or Coherence (89m, Sci-Fi/Thriller, Dark, English)
    # should be at the very top of the ranking
    assert top_title in ["Ex Machina", "Coherence", "Inception"]
    assert results[0]["total_score"] >= 80.0
    assert results[0]["score_breakdown"]["language_match"] == 15.0
    assert results[0]["score_breakdown"]["content_type_match"] == 10.0
    assert results[0]["score_breakdown"]["duration_match"] == 10.0
