from typing import List, Optional

from fastapi import APIRouter, Depends

from pydantic import BaseModel

from sqlalchemy.orm import Session

from backend.app.ai_service import run_ai_analysis

from backend.app.database import get_db

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatTurn(BaseModel):
    question: str
    explanation: Optional[str] = None


class AIQuery(BaseModel):
    question: str
    history: Optional[List[ChatTurn]] = None


@router.post("/query")
def ai_query(request: AIQuery, db: Session = Depends(get_db)):
    history_payload = (
        [turn.model_dump() for turn in request.history] if request.history else None
    )

    result = run_ai_analysis(request.question, history_payload, db)

    return {
        "question": request.question,
        "title": result["title"],
        "explanation": result["explanation"],
        "chart": result["chart"],
        "follow_up_questions": result["follow_up_questions"],
        "steps": result["steps"],
    }
