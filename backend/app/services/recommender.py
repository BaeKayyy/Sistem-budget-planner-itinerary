from pathlib import Path
import pickle

import pandas as pd


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
