"""AI chatbot module — service layer."""

from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.rag_pipeline import (
    GEMINI_UNAVAILABLE_RESPONSE,
    LLM_SERVICE_UNAVAILABLE_RESPONSE,
    LOCAL_LLM_UNAVAILABLE_RESPONSE,
    query_rag,
)
from app.modules.ai.models import ChatMessage, ChatSession
from app.utils.logger import get_logger

logger = get_logger(__name__)


from app.modules.ai.guardrails import is_question_allowed_locally, BLOCKED_RESPONSE
from app.modules.ai.models import FAQEntry


LOW_CONFIDENCE_ANSWER_MARKERS = (
    "I don't have enough context to answer your question right now.",
    GEMINI_UNAVAILABLE_RESPONSE,
    LLM_SERVICE_UNAVAILABLE_RESPONSE,
    LOCAL_LLM_UNAVAILABLE_RESPONSE,
    BLOCKED_RESPONSE,
)


def _should_cache_faq_answer(answer: str) -> bool:
    """Cache only useful generated answers, not guardrail or service failure text."""
    return bool(answer and not any(marker in answer for marker in LOW_CONFIDENCE_ANSWER_MARKERS))


async def ask_question(
    db: AsyncSession,
    user_id: int,
    question: str,
    session_id: Optional[int] = None,
    course_id: Optional[int] = None,
) -> dict:
    """Process a user question through the RAG pipeline and persist the conversation."""
    # Get or create chat session
    if session_id:
        session = await db.get(ChatSession, session_id)
        if session is None or session.user_id != user_id:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        session = ChatSession(
            user_id=user_id,
            title=question[:100],
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)

    # Server-side guardrails validation (check allowed/blocked topics before querying RAG/OpenAI)
    if not is_question_allowed_locally(question):
        # Save user message to history
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=question,
        )
        db.add(user_msg)
        
        # Save blocked assistant message to history
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=BLOCKED_RESPONSE,
        )
        db.add(assistant_msg)
        await db.flush()
        
        logger.info("ai_question_blocked_by_guardrails", user_id=user_id, session_id=session.id)
        return {
            "session_id": session.id,
            "answer": BLOCKED_RESPONSE,
            "sources": [],
        }

    # 1. Simple Dynamic FAQ Match
    # Fetch all active FAQs to do a simplistic dynamic match
    faq_res = await db.execute(select(FAQEntry).where(FAQEntry.is_active == True))
    all_faqs = faq_res.scalars().all()
    
    # Simple direct match (for a real prod app, use embeddings/vector similarity)
    matched_faq = None
    q_lower = question.lower().strip()
    for f in all_faqs:
        if q_lower == f.question.lower().strip() or f.question.lower().strip() in q_lower:
            matched_faq = f
            break
            
    if matched_faq:
        matched_faq.frequency += 1
        await db.flush()
        answer = matched_faq.answer
        sources = [f"FAQ - freq: {matched_faq.frequency}"]
    else:
        # Run RAG pipeline
        rag_result = await query_rag(question)
        answer = rag_result["answer"]
        sources = rag_result.get("sources", [])
        
        if _should_cache_faq_answer(answer):
            new_faq = FAQEntry(question=question, answer=answer, frequency=1)
            db.add(new_faq)
            await db.flush()
        else:
            logger.info("ai_answer_not_cached", user_id=user_id, session_id=session.id)

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    
    # Save assistant message
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
    )
    db.add(assistant_msg)
    await db.flush()

    logger.info("ai_question_answered", user_id=user_id, session_id=session.id)

    return {
        "session_id": session.id,
        "answer": answer,
        "sources": sources,
    }


async def get_chat_history(db: AsyncSession, user_id: int) -> List[ChatSession]:
    """Get all chat sessions with messages for a user."""
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
    )
    return list(result.scalars().all())

async def get_faqs(db: AsyncSession) -> List["FAQEntry"]:
    from app.modules.ai.models import FAQEntry
    """Get FAQs sorted by frequency."""
    result = await db.execute(
        select(FAQEntry).where(FAQEntry.is_active == True).order_by(FAQEntry.frequency.desc()).limit(20)
    )
    return list(result.scalars().all())


async def ask_question_public(
    db: AsyncSession,
    question: str,
) -> dict:
    """Process a public visitor question through guardrails and the RAG pipeline."""
    # Server-side guardrails validation
    if not is_question_allowed_locally(question):
        return {
            "answer": (
                "I am only trained to assist with topics covered in our courses and trading education. "
                "For out-of-the-box questions or general support, please contact our team at "
                "support@fintrade.com or call us at +91 92746 75947."
            ),
            "sources": ["contact-support"],
        }

    # Match FAQ dynamically
    faq_res = await db.execute(select(FAQEntry).where(FAQEntry.is_active == True))
    all_faqs = faq_res.scalars().all()
    
    matched_faq = None
    q_lower = question.lower().strip()
    for f in all_faqs:
        if q_lower == f.question.lower().strip() or f.question.lower().strip() in q_lower:
            matched_faq = f
            break
            
    if matched_faq:
        matched_faq.frequency += 1
        await db.flush()
        return {
            "answer": matched_faq.answer,
            "sources": [f"FAQ - freq: {matched_faq.frequency}"],
        }

    # Run RAG pipeline
    rag_result = await query_rag(question)
    answer = rag_result["answer"]
    sources = rag_result.get("sources", [])

    # Out of the box detection: check for low confidence markers
    if any(marker in answer for marker in LOW_CONFIDENCE_ANSWER_MARKERS):
        return {
            "answer": (
                "I don't have enough context to answer your question right now. "
                "For further assistance regarding our website or courses, please contact our team at "
                "support@fintrade.com or call us at +91 92746 75947."
            ),
            "sources": ["contact-support"],
        }

    return {
        "answer": answer,
        "sources": sources[:3],
    }

