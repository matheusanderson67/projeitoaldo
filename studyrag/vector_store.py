import numpy as np

from . import config

_model = None


def _get_model():
    global _model
    if _model is None: 
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def embed(texts) -> np.ndarray:
    vecs = _get_model().encode(
        list(texts), normalize_embeddings=True, batch_size=32, show_progress_bar=False
    )
    return np.asarray(vecs, dtype=np.float32)
