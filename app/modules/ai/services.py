"""AI chatbot module — service layer."""

from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.rag_pipeline import query_rag
from app.modules.ai.models import ChatMessage, ChatSession
from app.utils.logger import get_logger

logger = get_logger(__name__)


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

    # 1. Simple Dynamic FAQ Match
    from app.modules.ai.models import FAQEntry
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
        sources = [{"source": f"FAQ - freq: {matched_faq.frequency}"}]
    else:
        # Run RAG pipeline
        rag_result = await query_rag(question)
        answer = rag_result["answer"]
        sources = rag_result.get("sources", [])
        
        # Add new question to FAQ dynamically
        new_faq = FAQEntry(question=question, answer=answer, frequency=1)
        db.add(new_faq)
        await db.flush()

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
