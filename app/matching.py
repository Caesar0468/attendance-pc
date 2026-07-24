import numpy as np


def compute_similarity(emb1: list[float], emb2: list[float]) -> float:
    v1 = np.array(emb1, dtype=np.float32)
    v2 = np.array(emb2, dtype=np.float32)
    norm1, norm2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


def match_face(
    face_embedding: list[float],
    worker_embeddings: list[tuple[int, list[list[float]]]],
    similarity_threshold: float,
    uncertain_threshold: float,
) -> tuple[str, int | None, float]:
    best_worker_id = None
    highest_similarity = -1.0

    for worker_id, embeddings_list in worker_embeddings:
        for stored_emb in embeddings_list:
            sim = compute_similarity(face_embedding, stored_emb)
            if sim > highest_similarity:
                highest_similarity = sim
                best_worker_id = worker_id

    if highest_similarity >= similarity_threshold:
        return ("matched", best_worker_id, highest_similarity)
    elif highest_similarity >= uncertain_threshold:
        return ("uncertain", best_worker_id, highest_similarity)

    return ("unmatched", None, highest_similarity)