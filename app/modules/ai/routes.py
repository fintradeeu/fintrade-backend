"""AI chatbot module — API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.ai import schemas, services

router = APIRouter(prefix="/ai", tags=["AI Chatbot"])


@router.post("/ask", response_model=schemas.AskResponse)
async def ask(
    body: schemas.AskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ask the AI chatbot a question (RAG-powered)."""
    result = await services.ask_question(
        db,
        user_id=current_user.id,
        question=body.question,
        session_id=body.session_id,
        course_id=body.course_id,
    )
    return schemas.AskResponse(**result)


@router.post("/public/ask")
async def ask_public(
    body: schemas.AskRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ask the public AI chatbot a question (RAG-powered, no authentication)."""
    result = await services.ask_question_public(
        db,
        question=body.question,
    )
    return result



@router.get("/chat-history", response_model=schemas.ChatHistoryResponse)
async def chat_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's chat history."""
    sessions = await services.get_chat_history(db, current_user.id)
    return schemas.ChatHistoryResponse(
        sessions=[schemas.ChatSessionResponse.model_validate(s) for s in sessions]
    )

from typing import List

@router.get("/faqs", response_model=List[schemas.FAQResponse])
async def get_faqs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the top dynamically generated FAQs."""
    faqs = await services.get_faqs(db)
    return [schemas.FAQResponse.model_validate(f) for f in faqs]
