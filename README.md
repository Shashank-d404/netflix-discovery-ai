# AI-Powered Personalized Content Discovery

> **NETFLIX — The Discovery Problem**

A student-built AI project prototype that addresses streaming-platform catalog fatigue by combining natural-language preference extraction with a deterministic, catalog-grounded recommendation engine.

> **Academic prototype:** This project is an independent student prototype inspired by the stated “NETFLIX — The Discovery Problem” project theme. It is **not an official Netflix product or system**.

## Problem Statement

Large streaming catalogs can make content discovery difficult. Users may know what they want in natural language—for example, a dark science-fiction thriller in English under two hours—but still have to manually search through many titles and filters.

This project explores a lightweight AI-assisted solution:

**User preference → preference extraction → verified catalog preferences → deterministic ranking → personalized recommendations**

The system keeps recommendation candidates grounded in a local content catalog rather than allowing an AI model to invent titles.

## Project Overview

The application provides two ways to request recommendations:

1. **Natural-language discovery** — describe what you want in ordinary language.
2. **Structured discovery** — select filters such as genre, language, content type, mood, and maximum duration.

Google Gemini is used for natural-language preference extraction when an API key is available. Final title selection and ranking are performed by the deterministic Python recommendation engine.

## Key Features

- Natural-language content discovery
- Structured preference filters
- AI-assisted preference extraction using Google Gemini
- Deterministic recommendation ranking
- Catalog-grounded recommendations
- Transparent recommendation score breakdown
- Match reasons for recommended titles
- Genre, mood, language, content-type, and duration matching
- Quality-rating contribution to the score
- Offline heuristic fallback when Gemini is unavailable
- Catalog taxonomy validation
- REST-style JSON API
- Interactive web frontend
- Automated test suite

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Python, Flask |
| AI/NLP | Google Gemini API |
| Recommendation logic | Deterministic Python scoring |
| Data | JSON |
| Testing | Pytest |
| Version control | Git / GitHub |
| Environment configuration | `.env` + `python-dotenv` |

## System Architecture

```text
Web Frontend
HTML + CSS + Vanilla JS
        |
        | HTTP / JSON
        v
Flask Backend
app.py / API routes
        |
        +----------------+
        |                |
        v                v
Gemini Service      Catalog Service
Preference          Load + validate
extraction          + index catalog
        |                |
        +-------+--------+
                v
        Recommendation Engine
        Deterministic scoring
                |
                v
        Ranked catalog results
AI Workflow

For a natural-language request such as:

I want a dark sci-fi thriller in English, preferably a movie under two hours.

the system:

Receives the request through POST /api/recommend/natural.
Uses Gemini to extract structured preferences when available.
Validates extracted values against supported catalog taxonomies.
Uses the deterministic recommendation engine to evaluate catalog titles.
Returns recommendations with scores, reasons, metadata, and extraction mode.

Gemini does not choose or invent the final titles.

Recommendation Scoring

The recommendation engine uses a transparent 100-point scoring model:

Factor	Maximum points
Genre match	35
Mood / tags match	25
Language match	15
Content type match	10
Duration match	10
Quality-rating contribution	5
Total	100

Optional preferences are not treated as mismatches when the user does not provide them.

The score is a project-defined match score, not a prediction of what a real streaming platform would recommend.

Catalog Grounding

Recommendations are grounded in the project's local catalog.

The recommendation engine only returns titles that exist in:

data/catalog.json

The AI model is used for preference extraction rather than generating arbitrary movie or series titles.

The project does not claim zero hallucinations or guaranteed correctness.

Gemini Fallback

The application can remain usable when Gemini cannot be used.

Fallback conditions include:

GEMINI_API_KEY is not configured
Gemini request failure
timeout or API error
malformed or unparseable model output

In those situations, the backend uses an offline heuristic extraction path based on supported catalog taxonomies and common input variations.

The API identifies the extraction mode so the frontend can distinguish Gemini processing from offline fallback processing.

API Endpoints
GET /

Serves the web application.

GET /api/health

Returns backend health information.

GET /api/catalog/filters

Returns supported catalog filters and taxonomies.

GET /api/catalog/items

Returns catalog items.

POST /api/recommend

Accepts structured recommendation preferences.

Example:

{
  "genres": ["Sci-Fi", "Thriller"],
  "language": "English",
  "content_type": "Movie",
  "mood": "Dark",
  "max_duration": 120,
  "top_n": 5
}
POST /api/recommend/natural

Accepts a natural-language discovery request.

Example:

{
  "query": "I want a dark sci-fi thriller in English, preferably a movie under two hours",
  "top_n": 5
}
Project Structure
netflix-discovery-ai/
├── app.py
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── data/
│   ├── catalog.json
│   └── catalog_schema.json
│
├── services/
│   ├── __init__.py
│   ├── catalog_service.py
│   ├── gemini_service.py
│   └── recommender.py
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
│
├── templates/
│   └── index.html
│
└── tests/
    ├── __init__.py
    ├── test_api.py
    ├── test_catalog.py
    ├── test_gemini.py
    └── test_recommender.py
Installation
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd netflix-discovery-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
Environment Configuration

Create a local .env file:

GEMINI_API_KEY=your_api_key_here

The project provides .env.example as a template.

Never commit your real API key.

The .gitignore excludes .env and the Python virtual environment from Git tracking.

If a Gemini API key is not provided, the application can use its offline heuristic fallback for natural-language extraction.

Running the Application

Activate the virtual environment:

source .venv/bin/activate

Start Flask:

python app.py

Then open the local address shown by Flask in your browser.

Running Tests

Run the complete test suite with:

python -m pytest -q

Current verified project state:

61 passed

The test suite covers catalog loading and validation, recommendation scoring, Gemini/fallback behavior, and API behavior.

Testing Philosophy

Tests cover:

catalog loading
catalog schema validation
invalid catalog handling
preference sanitization
recommendation scoring
score breakdowns
match reasons
ranking and tie-breaking
API request validation
API response structure
Gemini service behavior
fallback extraction
natural-language recommendation flow

External Gemini network access is not required for the automated test suite.

Frontend

The frontend provides:

project introduction
live backend/AI status
natural-language prompt input
structured filters
supported genre, mood, and language options
recommendation count selection
extraction audit information
recommendation cards
match scores
metadata and synopsis
score breakdown visualization
system workflow explanation
AI transparency and academic disclaimer

The frontend communicates with the Flask backend using JSON requests.

AI Transparency

The project separates AI-assisted interpretation from deterministic recommendation ranking.

Gemini is responsible for:
interpreting natural-language preferences
extracting structured user intent
Python recommendation logic is responsible for:
selecting candidates from the local catalog
calculating recommendation scores
ranking candidates
producing score breakdowns and match reasons

This separation makes the recommendation process easier to inspect and test.

Security Considerations
API credentials are loaded from environment variables.
.env is excluded from Git.
.env.example contains only configuration structure.
Secrets are not intended to be exposed through API responses.
The Gemini API key is not required by the frontend.
Generated AI preferences are validated against supported catalog taxonomies.

This is an academic prototype and has not undergone a production security audit.

Limitations
The catalog is curated locally rather than being a live streaming catalog.
Recommendations are limited to titles present in the local dataset.
The scoring model is a project-defined heuristic, not a trained production recommendation model.
Gemini extraction quality depends on the configured API and model behavior.
Offline fallback uses heuristic pattern matching and is less flexible than an LLM.
The project does not represent Netflix's internal recommendation architecture.
No claim is made that the recommendations reproduce Netflix's real-world ranking behavior.
The project is not production-ready software.
Future Improvements

Possible future development includes:

larger and externally sourced datasets
user profiles and persistent preferences
collaborative filtering
embedding-based semantic retrieval
vector databases
richer preference learning
recommendation feedback loops
explanation quality improvements
authentication
database-backed catalog management
cloud deployment
performance and security hardening
evaluation using recommendation-system metrics
Academic Disclaimer

This project was developed as a student project prototype for:

NETFLIX — The Discovery Problem

It is an independent implementation for educational purposes.

It is not affiliated with, sponsored by, endorsed by, or developed by Netflix.

Netflix names and concepts are referenced only to describe the assigned project problem context.

Project Status
Curated content catalog
Catalog schema validation
Deterministic recommendation engine
Recommendation scoring breakdown
Flask backend
Structured recommendation API
Natural-language recommendation API
Gemini integration
Offline fallback extraction
Interactive frontend
Automated tests
Security/secrets configuration
Project documentation
Current verified test result

61 tests passed.

License

This project is an academic/student prototype. Add an appropriate open-source license if the project is intended to be distributed publicly.
