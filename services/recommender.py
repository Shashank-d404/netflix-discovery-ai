"""Deterministic recommendation engine for the Netflix Discovery system.

Calculates multi-factor transparent scores (0 to 100 points) based on:
  - Genre match: 35 points
  - Mood / Tag match: 25 points
  - Language match: 15 points
  - Content type match: 10 points
  - Duration compatibility: 10 points
  - Rating quality boost: 5 points

Guarantees:
  1. Zero hallucination: Only items from the catalog are evaluated and returned.
  2. 100% explainability: Full score breakdowns and matched reasons are preserved.
  3. Deterministic ranking: Exact and stable tie-breaking.
  4. Graceful handling of missing/optional user preferences without unfair penalties.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from services.catalog_service import CatalogService, get_catalog_service

# Maximum possible points per factor (Sum = 100.0)
WEIGHT_GENRE = 35.0
WEIGHT_MOOD = 25.0
WEIGHT_LANGUAGE = 15.0
WEIGHT_CONTENT_TYPE = 10.0
WEIGHT_DURATION = 10.0
WEIGHT_RATING = 5.0


@dataclass
class UserPreferences:
    """Structured user preferences for content discovery."""

    genres: List[str] = field(default_factory=list)
    language: Optional[str] = None
    content_type: Optional[str] = None
    moods: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    max_duration_minutes: Optional[int] = None
    duration_category: Optional[str] = None  # 'quick', 'standard', 'epic', 'any'

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "UserPreferences":
        """Builds a UserPreferences instance safely from a dictionary."""
        if not data or not isinstance(data, dict):
            return cls()

        def _to_list(val: Any) -> List[str]:
            if val is None:
                return []
            if isinstance(val, str):
                parts = [p.strip() for p in val.split(",") if p.strip()]
                return parts if parts else ([val.strip()] if val.strip() else [])
            if isinstance(val, (list, tuple, set)):
                return [str(item).strip() for item in val if str(item).strip()]
            return []

        # Parse duration
        max_duration = data.get("max_duration_minutes") or data.get("max_duration")
        try:
            max_duration = int(max_duration) if max_duration is not None and int(max_duration) > 0 else None
        except (ValueError, TypeError):
            max_duration = None

        return cls(
            genres=_to_list(data.get("genres")),
            language=str(data["language"]).strip() if data.get("language") else None,
            content_type=str(data["content_type"]).strip() if data.get("content_type") else None,
            moods=_to_list(data.get("moods") or data.get("mood")),
            tags=_to_list(data.get("tags")),
            max_duration_minutes=max_duration,
            duration_category=str(data.get("duration_category", "")).strip().lower() or None,
        )


def score_genre(
    user_genres: Sequence[str], item_genres: Sequence[str]
) -> Tuple[float, List[str]]:
    """Calculates genre match score (up to 35.0 pts).

    If the user specified no genres, awards full points (no penalty for missing preference).
    Otherwise, calculates proportional overlap.
    """
    clean_user = {g.strip().lower() for g in user_genres if g and g.strip()}
    if not clean_user:
        return WEIGHT_GENRE, []

    item_map = {g.strip().lower(): g for g in item_genres if g and g.strip()}
    matched_keys = clean_user.intersection(item_map.keys())
    matched_genres = [item_map[k] for k in matched_keys]

    overlap_ratio = len(matched_keys) / len(clean_user)
    score = round(WEIGHT_GENRE * overlap_ratio, 2)
    return score, sorted(matched_genres)


def score_mood_and_tags(
    user_moods: Sequence[str],
    user_tags: Sequence[str],
    item_moods: Sequence[str],
    item_tags: Sequence[str],
) -> Tuple[float, List[str], List[str]]:
    """Calculates mood and tag match score (up to 25.0 pts).

    If no mood/tags requested, awards full points.
    Matches user targets across both item moods and item tags.
    """
    clean_user_moods = {m.strip().lower() for m in user_moods if m and m.strip()}
    clean_user_tags = {t.strip().lower() for t in user_tags if t and t.strip()}
    all_user_targets = clean_user_moods.union(clean_user_tags)

    if not all_user_targets:
        return WEIGHT_MOOD, [], []

    item_mood_map = {m.strip().lower(): m for m in item_moods if m and m.strip()}
    item_tag_map = {t.strip().lower(): t for t in item_tags if t and t.strip()}
    all_item_keys = set(item_mood_map.keys()).union(item_tag_map.keys())

    matched_keys = all_user_targets.intersection(all_item_keys)
    matched_moods = [item_mood_map[k] for k in matched_keys if k in item_mood_map]
    matched_tags = [item_tag_map[k] for k in matched_keys if k in item_tag_map]

    overlap_ratio = len(matched_keys) / len(all_user_targets)
    score = round(WEIGHT_MOOD * min(1.0, overlap_ratio), 2)
    return score, sorted(matched_moods), sorted(matched_tags)


def score_language(
    user_lang: Optional[str], item_lang: Optional[str]
) -> Tuple[float, bool]:
    """Calculates language match score (up to 15.0 pts).

    If language is unspecified or 'Any', awards full points.
    """
    if not user_lang:
        return WEIGHT_LANGUAGE, True

    norm_user = user_lang.strip().lower()
    if norm_user in {"any", "all", "both", ""}:
        return WEIGHT_LANGUAGE, True

    norm_item = str(item_lang).strip().lower() if item_lang else ""
    if norm_user == norm_item:
        return WEIGHT_LANGUAGE, True

    return 0.0, False


def score_content_type(
    user_type: Optional[str], item_type: Optional[str]
) -> Tuple[float, bool]:
    """Calculates content type score (up to 10.0 pts).

    If content type is unspecified or 'Any', awards full points.
    """
    if not user_type:
        return WEIGHT_CONTENT_TYPE, True

    norm_user = user_type.strip().lower()
    if norm_user in {"any", "all", "both", ""}:
        return WEIGHT_CONTENT_TYPE, True

    norm_item = str(item_type).strip().lower() if item_type else ""
    if norm_user == norm_item:
        return WEIGHT_CONTENT_TYPE, True

    return 0.0, False


def score_duration(
    max_duration_minutes: Optional[int],
    duration_category: Optional[str],
    item_duration_minutes: Optional[int],
) -> Tuple[float, bool]:
    """Calculates duration compatibility score (up to 10.0 pts).

    If no duration limit specified, awards full points.
    Applies continuous, graceful penalty for runtimes exceeding preferred limits.
    """
    if item_duration_minutes is None or item_duration_minutes <= 0:
        return WEIGHT_DURATION, True

    # Derive effective max limit
    effective_max = max_duration_minutes
    if not effective_max and duration_category:
        cat = duration_category.strip().lower()
        if cat == "quick":
            effective_max = 90
        elif cat == "standard":
            effective_max = 120
        elif cat == "epic":
            # For epic, item >= 120 mins gets full score
            if item_duration_minutes >= 120:
                return WEIGHT_DURATION, True
            underage = 120 - item_duration_minutes
            penalty = (underage / 30.0) * 5.0
            return round(max(0.0, WEIGHT_DURATION - penalty), 2), False

    if not effective_max or effective_max <= 0:
        return WEIGHT_DURATION, True

    if item_duration_minutes <= effective_max:
        return WEIGHT_DURATION, True

    # Continuous penalty: 5 pts per 30 minutes overage
    overage = item_duration_minutes - effective_max
    penalty = (overage / 30.0) * 5.0
    score = round(max(0.0, WEIGHT_DURATION - penalty), 2)
    return score, score >= 7.0


def score_rating(item_rating: Optional[float | int]) -> float:
    """Calculates rating quality boost (up to 5.0 pts).

    Formula: (rating / 10.0) * 5.0
    """
    if item_rating is None:
        return 0.0
    try:
        r = float(item_rating)
        r_bounded = max(0.0, min(10.0, r))
        return round((r_bounded / 10.0) * WEIGHT_RATING, 2)
    except (ValueError, TypeError):
        return 0.0


class RecommendationEngine:
    """Deterministic recommendation engine operating on a verified catalog."""

    def __init__(self, catalog_service: Optional[CatalogService] = None) -> None:
        self.catalog_service = catalog_service or get_catalog_service()

    def score_item(
        self, item: Dict[str, Any], prefs: UserPreferences
    ) -> Dict[str, Any]:
        """Evaluates and scores an individual catalog item against user preferences.

        Returns a detailed dictionary containing original metadata, total_score,
        score_breakdown, and match_reasons for explainability.
        """
        genre_pts, matched_genres = score_genre(prefs.genres, item.get("genres", []))
        mood_pts, matched_moods, matched_tags = score_mood_and_tags(
            prefs.moods, prefs.tags, item.get("moods", []), item.get("tags", [])
        )
        lang_pts, lang_matched = score_language(prefs.language, item.get("language"))
        type_pts, type_matched = score_content_type(
            prefs.content_type, item.get("type")
        )
        duration_pts, duration_compatible = score_duration(
            prefs.max_duration_minutes,
            prefs.duration_category,
            item.get("duration_minutes"),
        )
        rating_pts = score_rating(item.get("rating"))

        total_score = round(
            genre_pts + mood_pts + lang_pts + type_pts + duration_pts + rating_pts, 2
        )
        # Ensure strict bounds
        total_score = max(0.0, min(100.0, total_score))

        breakdown = {
            "genre_match": genre_pts,
            "mood_match": mood_pts,
            "language_match": lang_pts,
            "content_type_match": type_pts,
            "duration_match": duration_pts,
            "rating_boost": rating_pts,
        }

        match_reasons = {
            "matched_genres": matched_genres,
            "matched_moods": matched_moods,
            "matched_tags": matched_tags,
            "language_matched": lang_matched,
            "type_matched": type_matched,
            "duration_compatible": duration_compatible,
        }

        result = dict(item)
        result["total_score"] = total_score
        result["score_breakdown"] = breakdown
        result["match_reasons"] = match_reasons
        return result

    def recommend(
        self,
        preferences: Optional[UserPreferences | Dict[str, Any]] = None,
        top_n: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Generates ranked recommendations from the catalog.

        Args:
            preferences: User preferences object or raw dictionary.
            top_n: Maximum number of recommendations to return (default 5).
            min_score: Minimum total score threshold (default 0.0).

        Returns:
            List of scored catalog items sorted deterministically by score.
        """
        if isinstance(preferences, dict):
            prefs = UserPreferences.from_dict(preferences)
        elif isinstance(preferences, UserPreferences):
            prefs = preferences
        else:
            prefs = UserPreferences()

        raw_items = self.catalog_service.get_all_entries()
        if not raw_items:
            return []

        scored_items: List[Dict[str, Any]] = []
        for item in raw_items:
            scored = self.score_item(item, prefs)
            if scored["total_score"] >= min_score:
                scored_items.append(scored)

        # Deterministic sort order:
        # 1. Total score (highest first)
        # 2. Rating (highest first)
        # 3. Release year (newest first)
        # 4. Title (alphabetical)
        scored_items.sort(
            key=lambda x: (
                -x["total_score"],
                -float(x.get("rating", 0.0)),
                -int(x.get("release_year", 0)),
                str(x.get("title", "")).lower(),
            )
        )

        n = max(1, min(len(scored_items), top_n))
        return scored_items[:n]


_default_engine: Optional[RecommendationEngine] = None


def get_recommendation_engine(
    catalog_service: Optional[CatalogService] = None,
) -> RecommendationEngine:
    """Accessor for the default RecommendationEngine instance."""
    global _default_engine
    if _default_engine is None or catalog_service is not None:
        _default_engine = RecommendationEngine(catalog_service=catalog_service)
    return _default_engine
