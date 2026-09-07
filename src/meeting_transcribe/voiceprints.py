import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def compute_centroid(embeddings: list[list[float]]) -> list[float]:
    array = np.array(embeddings, dtype=np.float64)
    mean = array.mean(axis=0)
    norm = np.linalg.norm(mean)
    if norm == 0:
        return mean.tolist()
    return (mean / norm).tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=np.float64), np.array(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def load_voiceprints(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_voiceprint(path: Path, name: str, embedding: list[float], source: str) -> None:
    db = load_voiceprints(path)
    new_db = {
        **db,
        name: {
            "embedding": embedding,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(new_db, indent=2))


def match_speaker(
    embedding: list[float], db: dict, threshold: float
) -> tuple[str | None, float]:
    best_name: str | None = None
    best_score = 0.0
    for name, entry in db.items():
        score = cosine_similarity(embedding, entry["embedding"])
        if score > best_score:
            best_name, best_score = name, score
    if best_name is None or best_score < threshold:
        return None, best_score
    return best_name, best_score
