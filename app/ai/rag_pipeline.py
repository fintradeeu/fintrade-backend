"""RAG pipeline — Retrieval-Augmented Generation for the AI chatbot."""

from typing import List, Optional

from app.ai.embeddings import generate_embedding
from app.ai.vector_store import vector_store
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def query_rag(question: str, top_k: int = 3) -> dict:
    """Run the full RAG pipeline:
    1. Generate embedding for the user question
    2. Search the vector store for relevant context
    3. Generate a response using the LLM (or fallback)
    """
    # Step 1: Embed the question
    query_embedding = await generate_embedding(question)

    # Step 2: Retrieve relevant documents
    search_results = vector_store.search(query_embedding, top_k=top_k)
    context_chunks = [doc["text"] for doc, score in search_results if score > 0.3]
    sources = [doc.get("metadata", {}).get("source", "knowledge-base") for doc, score in search_results if score > 0.3]

    # Step 3: Generate answer
    if settings.OPENAI_API_KEY:
        answer = await _llm_generate(question, context_chunks)
    else:
        answer = _fallback_generate(question, context_chunks)

    return {
        "answer": answer,
        "sources": sources[:3],
    }


async def ingest_documents(documents: List[dict]) -> int:
    """Ingest documents into the vector store.

    Each document should have: {"text": str, "metadata": dict}
    """
    enriched = []
    for doc in documents:
        embedding = await generate_embedding(doc["text"])
        enriched.append({
            "text": doc["text"],
            "embedding": embedding,
            "metadata": doc.get("metadata", {}),
        })
    vector_store.add_documents(enriched)
    logger.info("rag_documents_ingested", count=len(enriched))
    return len(enriched)


async def _llm_generate(question: str, context_chunks: List[str]) -> str:
    """Generate an answer using OpenAI ChatCompletion with guardrails SYSTEM_PROMPT."""
    try:
        import openai
        from app.modules.ai.guardrails import SYSTEM_PROMPT

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        context = "\n\n---\n\n".join(context_chunks) if context_chunks else "No specific context available."

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}",
                },
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("llm_generation_failed", error=str(exc))
        return _fallback_generate(question, context_chunks)


def _fallback_generate(question: str, context_chunks: List[str]) -> str:
    """Offline fallback: return context-based answer without an LLM."""
    if context_chunks:
        combined = "\n".join(f"• {c[:200]}" for c in context_chunks[:3])
        return (
            f"Based on our knowledge base, here is relevant information for your question:\n\n"
            f"{combined}\n\n"
            f"For a more detailed answer, please ensure the AI service (OpenAI) is configured."
        )
    return (
        "I don't have enough context to answer your question right now. "
        "Please try rephrasing, or contact your instructor for help. "
        "Tip: Make sure course content and FAQs have been ingested into the knowledge base."
    )
