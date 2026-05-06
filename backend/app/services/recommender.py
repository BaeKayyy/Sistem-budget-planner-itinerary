from pathlib import Path
import pickle

import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


class RecommenderLoadError(RuntimeError):
    """Raised when recommender artifacts cannot be loaded."""


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = Path(__file__).resolve().parents[3]

DATA_DIR_CANDIDATES = (
    BACKEND_DIR / "data" / "processed",
    PROJECT_DIR / "data" / "processed",
)


def _get_data_dir() -> Path:
    for data_dir in DATA_DIR_CANDIDATES:
        if data_dir.exists():
            return data_dir

    checked_paths = ", ".join(str(path) for path in DATA_DIR_CANDIDATES)
    raise RecommenderLoadError(
        f"Processed data directory was not found. Checked: {checked_paths}"
    )


DATA_DIR = _get_data_dir()
DATASET_PATH = DATA_DIR / "tfidf_dataset.csv"
VECTORIZER_PATH = DATA_DIR / "tfidf_vectorizer.pkl"
MATRIX_PATH = DATA_DIR / "tfidf_matrix.pkl"
VALID_FILTER_TYPES = {"wisata", "kuliner", "hotel"}
MIN_SIMILARITY_SCORE = 0.1

QUERY_ENRICHMENTS = {
    "pantai": "beach",
    "cafe": "cafe",
    "kafe": "cafe",
    "kopi": "cafe coffee",
    "murah": "budget",
}

INTENT_RULES = {
    "pantai": ("pantai", "beach"),
    "cafe": ("cafe", "kafe", "kopi", "coffee"),
}


def _load_dataset() -> pd.DataFrame:
    try:
        # Dataset: cleaned item data used as the reference table for recommendations.
        return pd.read_csv(DATASET_PATH)
    except FileNotFoundError as exc:
        raise RecommenderLoadError(f"Dataset file was not found: {DATASET_PATH}") from exc
    except Exception as exc:
        raise RecommenderLoadError(f"Failed to load dataset: {exc}") from exc


def _load_pickle(path: Path, label: str):
    try:
        with path.open("rb") as file:
            return pickle.load(file)
    except FileNotFoundError as exc:
        raise RecommenderLoadError(f"{label} file was not found: {path}") from exc
    except Exception as exc:
        raise RecommenderLoadError(f"Failed to load {label}: {exc}") from exc


dataset = _load_dataset()

# Vectorizer: trained TF-IDF transformer that stores the text vocabulary.
tfidf_vectorizer = _load_pickle(VECTORIZER_PATH, "TF-IDF vectorizer")

# Matrix: TF-IDF feature matrix where each dataset row is represented numerically.
tfidf_matrix = _load_pickle(MATRIX_PATH, "TF-IDF matrix")


def get_system_status() -> dict:
    vocabulary = getattr(tfidf_vectorizer, "vocabulary_", {})

    return {
        "dataset_rows": len(dataset),
        "tfidf_matrix_shape": tfidf_matrix.shape,
        "vectorizer_vocabulary_size": len(vocabulary),
    }


def normalize_query(query: str) -> str:
    query = query.strip().lower()
    enriched_terms = []

    for keyword, enrichment in QUERY_ENRICHMENTS.items():
        if keyword in query:
            enriched_terms.append(enrichment)

    if not enriched_terms:
        return query

    return f"{query} {' '.join(enriched_terms)}"


def _validate_filter_type(filter_type: str | None) -> str | None:
    if filter_type is None:
        return None

    normalized_filter = filter_type.strip().lower()
    if normalized_filter not in VALID_FILTER_TYPES:
        valid_options = ", ".join(sorted(VALID_FILTER_TYPES))
        raise ValueError(f"Invalid filter_type. Use one of: {valid_options}")

    return normalized_filter


def _infer_type_from_query(query: str) -> str | None:
    if "hotel" in query:
        return "hotel"

    return None


def _apply_intent_filter(results: pd.DataFrame, query: str) -> pd.DataFrame:
    searchable_text = (
        results["name"].fillna("")
        + " "
        + results["category"].fillna("")
        + " "
        + results["subtypes"].fillna("")
        + " "
        + results["subtypes_clean"].fillna("")
        + " "
        + results["text"].fillna("")
    ).str.lower()

    for keyword, allowed_terms in INTENT_RULES.items():
        if keyword in query:
            pattern = "|".join(allowed_terms)
            results = results[searchable_text.str.contains(pattern, na=False)]

    return results


def _format_recommendation(row: pd.Series) -> dict:
    rating = row.get("rating")
    price_estimate = row.get("price_estimate")

    return {
        "name": row.get("name"),
        "type": row.get("type"),
        "rating": None if pd.isna(rating) else float(rating),
        "price_estimate": None if pd.isna(price_estimate) else int(price_estimate),
        "similarity_score": round(float(row.get("similarity_score")), 4),
    }


def recommend_places(
    query: str,
    filter_type: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    if top_k <= 0:
        return []

    normalized_filter = _validate_filter_type(filter_type)
    normalized_query = normalize_query(query)
    inferred_filter = _infer_type_from_query(normalized_query)

    if normalized_filter and inferred_filter and normalized_filter != inferred_filter:
        return []

    active_filter = normalized_filter or inferred_filter

    try:
        query_vector = tfidf_vectorizer.transform([normalized_query])
        similarity_scores = cosine_similarity(query_vector, tfidf_matrix).flatten()
    except Exception as exc:
        raise RecommenderLoadError(f"Failed to compute recommendations: {exc}") from exc

    results = dataset.copy()
    results["similarity_score"] = similarity_scores

    results = results.dropna(subset=["similarity_score"])
    results = results[results["similarity_score"] > MIN_SIMILARITY_SCORE]

    if active_filter:
        results = results[results["type"].str.lower() == active_filter]

    results = _apply_intent_filter(results, normalized_query)
    results = results.sort_values("similarity_score", ascending=False).head(top_k)

    if results.empty:
        return []

    return [_format_recommendation(row) for _, row in results.iterrows()]
