"""MODULE 3: Leadership readiness, AI recommendations, and market insights."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth_utils import get_current_user
from ..database import get_db
from ..models import (
    CareerDomain,
    MarketTrend,
    QuizAttempt,
    ReadinessHistory,
    RecommendationLog,
    RoadmapStep,
    StudentRoadmapProgress,
    User,
)

router = APIRouter(prefix="/api/leadership", tags=["Module 3: Leadership & Readiness"])


class RecommendationCreate(BaseModel):
    recommended_topic: str
    reason: str
    suggested_date: str | None = None


class RecommendationStatus(BaseModel):
    status: str


@router.get("/readiness-history")
def readiness_history(
    limit: int = 12,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ReadinessHistory)
        .filter(ReadinessHistory.user_id == current_user.id)
        .order_by(ReadinessHistory.recorded_at.desc())
        .limit(max(1, min(limit, 50)))
        .all()
    )
    return [
        {
            "id": r.id,
            "overall_score": r.overall_score,
            "category_scores": r.category_scores_json or {},
            "recorded_at": r.recorded_at.isoformat(),
        }
        for r in reversed(rows)
    ]


@router.get("/recommendations")
def list_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(RecommendationLog)
        .filter(RecommendationLog.user_id == current_user.id)
        .order_by(RecommendationLog.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "recommended_topic": r.recommended_topic,
            "reason": r.reason,
            "suggested_date": r.suggested_date,
            "pre_score": r.pre_score,
            "post_score": r.post_score,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/recommendations/generate")
def generate_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    weak_attempt = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.score_percent.asc())
        .first()
    )
    if weak_attempt:
        weak_topics = weak_attempt.weak_topics_json or []
        topic = weak_topics[0] if weak_topics else "Core concept review"
        reason = f"Your lowest recent quiz score was {weak_attempt.score_percent:.1f}%. "
        reason += "Focused practice can improve this weak area."
        pre_score = weak_attempt.score_percent
    else:
        topic = "Resume and interview fundamentals"
        reason = "Complete a career quiz to generate more personalized recommendations."
        pre_score = None

    recommendation = RecommendationLog(
        user_id=current_user.id,
        recommended_topic=topic,
        reason=reason,
        pre_score=pre_score,
        status="suggested",
    )
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    return {"id": recommendation.id, "recommended_topic": topic, "reason": reason}


@router.patch("/recommendations/{recommendation_id}")
def update_recommendation(
    recommendation_id: int,
    data: RecommendationStatus,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.status not in ("suggested", "followed", "improved"):
        raise HTTPException(status_code=422, detail="Invalid recommendation status.")
    row = db.query(RecommendationLog).filter(
        RecommendationLog.id == recommendation_id,
        RecommendationLog.user_id == current_user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    row.status = data.status
    db.commit()
    return {"message": "Recommendation updated.", "status": data.status}


@router.get("/market-trends")
def market_trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    domain = db.query(CareerDomain).filter(CareerDomain.name == current_user.selected_domain).first()
    query = db.query(MarketTrend)
    if domain:
        query = query.filter(MarketTrend.domain_id == domain.id)
    rows = query.all()
    return [
        {
            "role_title": r.role_title,
            "demand_index": r.demand_index,
            "in_demand_skills": r.in_demand_skills_json or [],
            "hiring_trend": r.hiring_trend_json or {},
            "source_name": r.source_name,
        }
        for r in rows
    ]
