"""Embedding utilities — generate text embeddings via OpenAI or fallback."""

from typing import List

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for the given text.

    Uses OpenAI embeddings API if the key is configured.
    Falls back to a deterministic hash-based pseudo-embedding for local dev.
    """
    if settings.AI_PROVIDER.lower() == "openai" and settings.OPENAI_API_KEY:
        return await _openai_embedding(text)
    return _fallback_embedding(text)


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Batch-generate embeddings."""
    return [await generate_embedding(t) for t in texts]


async def _openai_embedding(text: str) -> List[float]:
    """Call the OpenAI embeddings API."""
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.embeddings.create(
            input=text,
            model=settings.EMBEDDING_MODEL,
        )
        return response.data[0].embedding
    except Exception as exc:
        logger.error("openai_embedding_failed", error=str(exc))
        return _fallback_embedding(text)


def _fallback_embedding(text: str, dim: int = 384) -> List[float]:
    """Deterministic pseudo-embedding for offline / local development.

    NOT suitable for production — only provides basic similarity via hash bucketing.
    """
    import hashlib
    import struct

    h = hashlib.sha512(text.lower().encode()).digest()
    # Expand hash to fill `dim` floats
    floats = []
    for i in range(dim):
        # Cycle through hash bytes
        byte_idx = i % len(h)
        val = (h[byte_idx] + i) % 256
        floats.append((val / 255.0) * 2.0 - 1.0)  # normalise to [-1, 1]
    return floats
