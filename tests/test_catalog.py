"""Unit tests for catalog loading, validation, and querying."""

import json
import pytest
from pathlib import Path

from services.catalog_service import (
    CatalogService,
    CatalogNotFoundError,
    CatalogValidationError,
    get_catalog_service,
)


def test_default_catalog_loads_successfully():
    """Verify standard catalog loads and contains expected titles."""
    service = CatalogService()
    assert service.get_count() >= 30
    items = service.get_all_entries()
    assert len(items) == service.get_count()
    # Check first item has all required keys
    item = items[0]
    for key in [
        "id", "title", "type", "release_year", "genres", "language",
        "moods", "tags", "duration_minutes", "duration_display",
        "rating", "synopsis", "poster_gradient", "featured_cast"
    ]:
        assert key in item


def test_catalog_unique_taxonomies():
    """Verify genres, moods, and languages extraction."""
    service = CatalogService()
    genres = service.get_unique_genres()
    assert "Sci-Fi" in genres
    assert "Drama" in genres
    assert "Comedy" in genres

    languages = service.get_unique_languages()
    assert "English" in languages
    assert "Hindi" in languages

    types = service.get_unique_types()
    assert set(types) == {"Movie", "Series"}


def test_get_entry_by_id():
    """Verify looking up single items by id."""
    service = CatalogService()
    item = service.get_entry_by_id("mov-001")
    assert item is not None
    assert item["title"] == "Interstellar"
    assert item["type"] == "Movie"

    non_existent = service.get_entry_by_id("invalid-999")
    assert non_existent is None


def test_catalog_file_not_found(tmp_path):
    """Verify CatalogNotFoundError is raised when file is missing."""
    missing_file = tmp_path / "does_not_exist.json"
    with pytest.raises(CatalogNotFoundError):
        CatalogService(catalog_path=missing_file)


def test_catalog_malformed_json(tmp_path):
    """Verify CatalogValidationError when file contains corrupt JSON."""
    corrupt_file = tmp_path / "bad.json"
    corrupt_file.write_text("{ this is not valid json }", encoding="utf-8")
    with pytest.raises(CatalogValidationError, match="Malformed JSON"):
        CatalogService(catalog_path=corrupt_file)


def test_catalog_not_a_list(tmp_path):
    """Verify CatalogValidationError when JSON root is not an array."""
    dict_file = tmp_path / "dict_root.json"
    dict_file.write_text(json.dumps({"key": "val"}), encoding="utf-8")
    with pytest.raises(CatalogValidationError, match="must be a JSON array"):
        CatalogService(catalog_path=dict_file)


def test_catalog_duplicate_ids(tmp_path):
    """Verify duplicate IDs are rejected."""
    dup_file = tmp_path / "dup.json"
    items = [
        {
            "id": "mov-001",
            "title": "Movie 1",
            "type": "Movie",
            "release_year": 2020,
            "genres": ["Action"],
            "language": "English",
            "moods": ["Dark"],
            "tags": ["hero"],
            "duration_minutes": 100,
            "duration_display": "1h 40m",
            "rating": 8.0,
            "synopsis": "A great action movie synopsis.",
            "poster_gradient": "linear-gradient(135deg, #000, #fff)",
            "featured_cast": ["Actor A"]
        },
        {
            "id": "mov-001",  # Duplicate ID
            "title": "Movie 2",
            "type": "Movie",
            "release_year": 2021,
            "genres": ["Drama"],
            "language": "English",
            "moods": ["Emotional"],
            "tags": ["drama"],
            "duration_minutes": 110,
            "duration_display": "1h 50m",
            "rating": 7.5,
            "synopsis": "A drama movie synopsis here.",
            "poster_gradient": "linear-gradient(135deg, #000, #fff)",
            "featured_cast": ["Actor B"]
        }
    ]
    dup_file.write_text(json.dumps(items), encoding="utf-8")
    with pytest.raises(CatalogValidationError, match="Duplicate item ID"):
        CatalogService(catalog_path=dup_file)


def test_filter_candidates():
    """Verify candidate filtering by type."""
    service = CatalogService()
    movies_only = service.filter_candidates(content_type="Movie")
    assert all(item["type"] == "Movie" for item in movies_only)
    assert len(movies_only) > 0

    series_only = service.filter_candidates(content_type="Series")
    assert all(item["type"] == "Series" for item in series_only)
    assert len(series_only) > 0
