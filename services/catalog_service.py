"""Catalog service for loading, validating, and querying content metadata.

This service manages the in-memory content catalog loaded from data/catalog.json,
providing safe schema validation, query filters, and taxonomy extraction.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

REQUIRED_FIELDS = {
    "id": str,
    "title": str,
    "type": str,
    "release_year": int,
    "genres": list,
    "language": str,
    "moods": list,
    "tags": list,
    "duration_minutes": int,
    "duration_display": str,
    "rating": (int, float),
    "synopsis": str,
    "poster_gradient": str,
    "featured_cast": list,
}

VALID_TYPES = {"Movie", "Series"}


class CatalogError(Exception):
    """Base exception for catalog-related errors."""


class CatalogNotFoundError(CatalogError):
    """Raised when catalog file does not exist."""


class CatalogValidationError(CatalogError):
    """Raised when catalog data violates required schema."""


class CatalogService:
    """Service to load, validate, and access the content catalog."""

    def __init__(self, catalog_path: Optional[str | Path] = None) -> None:
        self.catalog_path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG_PATH
        self._items: List[Dict[str, Any]] = []
        self._items_by_id: Dict[str, Dict[str, Any]] = {}
        self.load_catalog()

    def load_catalog(self, path: Optional[str | Path] = None) -> None:
        """Safely loads and validates catalog.json.

        Args:
            path: Optional custom path to catalog file.

        Raises:
            CatalogNotFoundError: If catalog file is missing.
            CatalogValidationError: If catalog JSON is invalid or violates schema.
        """
        if path:
            self.catalog_path = Path(path)

        if not self.catalog_path.is_file():
            raise CatalogNotFoundError(
                f"Catalog file not found at: {self.catalog_path}"
            )

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise CatalogValidationError(
                f"Malformed JSON in catalog file {self.catalog_path}: {exc}"
            ) from exc

        if not isinstance(data, list):
            raise CatalogValidationError(
                f"Catalog root must be a JSON array, got {type(data).__name__}"
            )

        validated_items: List[Dict[str, Any]] = []
        items_by_id: Dict[str, Dict[str, Any]] = {}
        seen_ids: Set[str] = set()

        for idx, item in enumerate(data):
            validated_item = self._validate_item(item, index=idx)
            item_id = validated_item["id"]
            if item_id in seen_ids:
                raise CatalogValidationError(
                    f"Duplicate item ID detected: '{item_id}' at index {idx}"
                )
            seen_ids.add(item_id)
            validated_items.append(validated_item)
            items_by_id[item_id] = validated_item

        self._items = validated_items
        self._items_by_id = items_by_id

    @staticmethod
    def _validate_item(item: Any, index: int) -> Dict[str, Any]:
        """Validates a single catalog entry against expected schema."""
        if not isinstance(item, dict):
            raise CatalogValidationError(
                f"Item at index {index} must be a JSON object, got {type(item).__name__}"
            )

        for field, expected_type in REQUIRED_FIELDS.items():
            if field not in item:
                raise CatalogValidationError(
                    f"Missing required field '{field}' in item at index {index} (ID: {item.get('id', 'unknown')})"
                )
            if not isinstance(item[field], expected_type):
                raise CatalogValidationError(
                    f"Field '{field}' in item '{item.get('id', index)}' must be {expected_type}, "
                    f"got {type(item[field]).__name__}"
                )

        if item["type"] not in VALID_TYPES:
            raise CatalogValidationError(
                f"Invalid type '{item['type']}' in item '{item['id']}'. Allowed: {VALID_TYPES}"
            )

        if not (0.0 <= float(item["rating"]) <= 10.0):
            raise CatalogValidationError(
                f"Invalid rating {item['rating']} in item '{item['id']}'. Must be between 0.0 and 10.0"
            )

        if item["duration_minutes"] <= 0:
            raise CatalogValidationError(
                f"Invalid duration {item['duration_minutes']} in item '{item['id']}'. Must be > 0"
            )

        return item

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Returns all validated catalog entries as a list of copies."""
        return [dict(item) for item in self._items]

    def get_entry_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Finds a single catalog entry by its ID."""
        item = self._items_by_id.get(item_id)
        return dict(item) if item else None

    def get_count(self) -> int:
        """Returns the total number of catalog entries."""
        return len(self._items)

    def get_unique_genres(self) -> List[str]:
        """Returns sorted list of all unique genres present in the catalog."""
        genres: Set[str] = set()
        for item in self._items:
            genres.update(item.get("genres", []))
        return sorted(genres)

    def get_unique_languages(self) -> List[str]:
        """Returns sorted list of all unique languages present in the catalog."""
        languages = {item.get("language") for item in self._items if item.get("language")}
        return sorted(languages)

    def get_unique_moods(self) -> List[str]:
        """Returns sorted list of all unique moods present in the catalog."""
        moods: Set[str] = set()
        for item in self._items:
            moods.update(item.get("moods", []))
        return sorted(moods)

    def get_unique_types(self) -> List[str]:
        """Returns sorted list of content types present in the catalog."""
        types = {item.get("type") for item in self._items if item.get("type")}
        return sorted(types)

    def filter_candidates(
        self,
        content_type: Optional[str] = None,
        language: Optional[str] = None,
        max_duration: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Soft/hard filter candidate pool before scoring if needed."""
        results = self._items
        if content_type and content_type.lower() not in {"any", "all", ""}:
            results = [
                i for i in results if i.get("type", "").lower() == content_type.lower()
            ]
        return [dict(item) for item in results]


_default_service: Optional[CatalogService] = None


def get_catalog_service(catalog_path: Optional[str | Path] = None) -> CatalogService:
    """Singleton-style accessor for the default CatalogService instance."""
    global _default_service
    if _default_service is None or catalog_path is not None:
        _default_service = CatalogService(catalog_path=catalog_path)
    return _default_service
