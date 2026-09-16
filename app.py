"""Flask Application Entry Point for Netflix Discovery AI.

Provides RESTful endpoints for:
  - Health checks and system status
  - Available catalog filter taxonomies
  - Deterministic content recommendation scoring
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional
from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv

from services.catalog_service import (
    CatalogError,
    CatalogService,
    get_catalog_service,
)
from services.recommender import (
    RecommendationEngine,
    UserPreferences,
    get_recommendation_engine,
)
from services.gemini_service import (
    GeminiService,
    get_gemini_service,
)

# Load environment variables (.env) safely
load_dotenv()


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    """Application factory for the Netflix Discovery AI Flask server."""
    app = Flask(__name__, static_folder="static", template_folder="templates")

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-discovery-ai"),
        JSON_SORT_KEYS=False,
    )

    if test_config:
        app.config.update(test_config)

    # Initialize services
    catalog_path = app.config.get("CATALOG_PATH")
    catalog_service = (
        CatalogService(catalog_path=catalog_path)
        if catalog_path
        else get_catalog_service()
    )
    recommender_engine = RecommendationEngine(catalog_service=catalog_service)
    gemini_service = app.config.get("GEMINI_SERVICE") or get_gemini_service(
        api_key=app.config.get("GEMINI_API_KEY"),
        catalog_service=catalog_service,
    )

    # -------------------------------------------------------------------------
    # Error Handlers (Consistent JSON Error Envelopes)
    # -------------------------------------------------------------------------

    @app.errorhandler(400)
    def bad_request(error):
        msg = getattr(error, "description", "Bad Request")
        return jsonify({"success": False, "error": {"code": "BAD_REQUEST", "message": str(msg)}}), 400

    @app.errorhandler(404)
    def not_found(error):
        msg = getattr(error, "description", "Resource not found")
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": str(msg)}}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"success": False, "error": {"code": "METHOD_NOT_ALLOWED", "message": "HTTP method not allowed"}}), 405

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"success": False, "error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected server error occurred"}}), 500

    # -------------------------------------------------------------------------
    # Helper: Input Sanitization
    # -------------------------------------------------------------------------

    def _sanitize_string(val: Any, max_len: int = 100) -> Optional[str]:
        if not val or not isinstance(val, (str, int, float)):
            return None
        clean = str(val).strip()
        # Remove script and style tags along with their inner contents
        clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        # Remove any remaining HTML tags
        clean = re.sub(r"<[^>]+>", "", clean)
        clean = clean.strip()
        return clean[:max_len] if clean else None

    def _sanitize_string_list(val: Any, max_items: int = 15, max_item_len: int = 50) -> List[str]:
        if not val:
            return []
        if isinstance(val, str):
            val = [p.strip() for p in val.split(",") if p.strip()]
        if not isinstance(val, (list, tuple, set)):
            return []
        cleaned: List[str] = []
        for item in val:
            s = _sanitize_string(item, max_len=max_item_len)
            if s and s not in cleaned:
                cleaned.append(s)
            if len(cleaned) >= max_items:
                break
        return cleaned

    # -------------------------------------------------------------------------
    # Routes
    # -------------------------------------------------------------------------

    @app.route("/", methods=["GET"])
    def index():
        """Root endpoint. Serves web UI if template exists, else API welcome."""
        template_file = os.path.join(app.template_folder, "index.html")
        if os.path.isfile(template_file):
            return render_template("index.html")
        return jsonify({
            "project": "NETFLIX — The Discovery Problem",
            "concept": "AI-Powered Personalized Content Discovery System",
            "status": "online",
            "api_endpoints": [
                "/api/health",
                "/api/catalog/filters",
                "/api/catalog/items",
                "/api/recommend",
            ],
        })

    @app.route("/api/health", methods=["GET"])
    def health_check():
        """Health and system status check (never exposes keys)."""
        return jsonify({
            "success": True,
            "status": "healthy",
            "catalog_items_count": catalog_service.get_count(),
        })

    @app.route("/api/catalog/filters", methods=["GET"])
    def get_catalog_filters():
        """Retrieves available filter taxonomies extracted from the catalog."""
        return jsonify({
            "success": True,
            "filters": {
                "genres": catalog_service.get_unique_genres(),
                "languages": catalog_service.get_unique_languages(),
                "moods": catalog_service.get_unique_moods(),
                "content_types": catalog_service.get_unique_types(),
                "duration_presets": [
                    {"label": "Quick Watch (< 90m)", "value": "quick", "max_minutes": 90},
                    {"label": "Standard (90–120m)", "value": "standard", "max_minutes": 120},
                    {"label": "Epic / Long (> 120m)", "value": "epic", "max_minutes": None},
                ],
            },
        })

    @app.route("/api/catalog/items", methods=["GET"])
    def get_catalog_items():
        """Returns all catalog items."""
        return jsonify({
            "success": True,
            "count": catalog_service.get_count(),
            "items": catalog_service.get_all_entries(),
        })

    @app.route("/api/recommend", methods=["POST"])
    def get_recommendations():
        """Generates ranked content recommendations based on structured user preferences."""
        has_content = bool(request.data or request.form or (request.content_length and request.content_length > 0))

        if has_content:
            if not request.is_json:
                return jsonify({
                    "success": False,
                    "error": {
                        "code": "INVALID_CONTENT_TYPE",
                        "message": "Request Content-Type must be application/json",
                    },
                }), 400
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({
                    "success": False,
                    "error": {
                        "code": "MALFORMED_JSON",
                        "message": "Request payload contains malformed JSON",
                    },
                }), 400
        else:
            data = {}

        if not isinstance(data, dict):
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_PAYLOAD",
                    "message": "JSON body must be an object",
                },
            }), 400

        # Validate top_n
        raw_top_n = data.get("top_n", 5)
        try:
            top_n = int(raw_top_n)
            if not (1 <= top_n <= 20):
                return jsonify({
                    "success": False,
                    "error": {
                        "code": "INVALID_PARAM",
                        "message": "Parameter 'top_n' must be an integer between 1 and 20",
                    },
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_PARAM",
                    "message": "Parameter 'top_n' must be a valid integer",
                },
            }), 400

        # Validate max_duration_minutes if provided
        raw_max_dur = data.get("max_duration_minutes") or data.get("max_duration")
        max_duration_minutes: Optional[int] = None
        if raw_max_dur is not None:
            try:
                max_duration_minutes = int(raw_max_dur)
                if max_duration_minutes <= 0:
                    return jsonify({
                        "success": False,
                        "error": {
                            "code": "INVALID_PARAM",
                            "message": "Parameter 'max_duration_minutes' must be a positive integer",
                        },
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": {
                        "code": "INVALID_PARAM",
                        "message": "Parameter 'max_duration_minutes' must be a valid integer",
                    },
                }), 400

        # Sanitize structured preferences
        cleaned_genres = _sanitize_string_list(data.get("genres"))
        cleaned_moods = _sanitize_string_list(data.get("moods") or data.get("mood"))
        cleaned_tags = _sanitize_string_list(data.get("tags"))
        cleaned_language = _sanitize_string(data.get("language"))
        cleaned_type = _sanitize_string(data.get("content_type") or data.get("type"))
        cleaned_duration_cat = _sanitize_string(data.get("duration_category"))

        prefs = UserPreferences(
            genres=cleaned_genres,
            language=cleaned_language,
            content_type=cleaned_type,
            moods=cleaned_moods,
            tags=cleaned_tags,
            max_duration_minutes=max_duration_minutes,
            duration_category=cleaned_duration_cat,
        )

        recommendations = recommender_engine.recommend(prefs, top_n=top_n)

        return jsonify({
            "success": True,
            "count": len(recommendations),
            "preferences_applied": {
                "genres": prefs.genres,
                "language": prefs.language,
                "content_type": prefs.content_type,
                "moods": prefs.moods,
                "tags": prefs.tags,
                "max_duration_minutes": prefs.max_duration_minutes,
                "duration_category": prefs.duration_category,
            },
            "recommendations": recommendations,
        })

    @app.route("/api/recommend/natural", methods=["POST"])
    def get_natural_recommendations():
        """Generates recommendations from a natural-language query using Gemini with offline fallback."""
        has_content = bool(request.data or request.form or (request.content_length and request.content_length > 0))
        if not has_content:
            return jsonify({
                "success": False,
                "error": {
                    "code": "MISSING_PAYLOAD",
                    "message": "JSON body with 'query' field is required",
                },
            }), 400

        if not request.is_json:
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_CONTENT_TYPE",
                    "message": "Request Content-Type must be application/json",
                },
            }), 400

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_PAYLOAD",
                    "message": "JSON body must be an object",
                },
            }), 400

        raw_query = data.get("query")
        clean_query = _sanitize_string(raw_query, max_len=300)
        if not clean_query:
            return jsonify({
                "success": False,
                "error": {
                    "code": "EMPTY_QUERY",
                    "message": "Field 'query' must be a non-empty string",
                },
            }), 400

        # Validate top_n
        raw_top_n = data.get("top_n", 5)
        try:
            top_n = int(raw_top_n)
            if not (1 <= top_n <= 20):
                return jsonify({
                    "success": False,
                    "error": {
                        "code": "INVALID_PARAM",
                        "message": "Parameter 'top_n' must be an integer between 1 and 20",
                    },
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_PARAM",
                    "message": "Parameter 'top_n' must be a valid integer",
                },
            }), 400

        # Run preference extraction (Gemini or local heuristic fallback)
        extraction = gemini_service.extract_preferences(clean_query)
        recommendations = recommender_engine.recommend(extraction.preferences, top_n=top_n)

        return jsonify({
            "success": True,
            "query": clean_query,
            "extraction_mode": extraction.extraction_mode,
            "fallback_used": extraction.fallback_used,
            "fallback_reason": extraction.fallback_reason,
            "extracted_preferences": {
                "genres": extraction.preferences.genres,
                "language": extraction.preferences.language,
                "content_type": extraction.preferences.content_type,
                "moods": extraction.preferences.moods,
                "tags": extraction.preferences.tags,
                "max_duration_minutes": extraction.preferences.max_duration_minutes,
                "duration_category": extraction.preferences.duration_category,
            },
            "count": len(recommendations),
            "recommendations": recommendations,
        })

    return app


# Application instance for development / gunicorn / flask run
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
