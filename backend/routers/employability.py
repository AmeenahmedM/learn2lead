"""MODULE 2: Employability career roadmaps and placement readiness."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth_utils import get_current_user
from ..database import get_db
from ..models import (
    CareerDomain,
    Quiz,
    QuizAttempt,
    ReadinessConfig,
    ReadinessHistory,
    RoadmapStep,
    StudentRoadmapProgress,
    User,
)

router = APIRouter(prefix="/api/employability", tags=["Module 2: Employability"])


class DomainSelect(BaseModel):
    domain_id: int


class RoadmapStatusUpdate(BaseModel):
    status: str


def category_average(db: Session, user_id: int, categories: list[str]) -> float:
    attempts = (
        db.query(QuizAttempt)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(QuizAttempt.user_id == user_id, Quiz.category.in_(categories))
        .all()
    )
    if not attempts:
        return 0.0
    return round(sum(a.score_percent for a in attempts) / len(attempts), 1)


@router.get("/domains")
def list_domains(db: Session = Depends(get_db)):
    domains = db.query(CareerDomain).order_by(CareerDomain.name).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "growth_rate_percent": d.growth_rate_percent,
            "avg_salary_range": d.avg_salary_range,
        }
        for d in domains
    ]


@router.post("/domains/select")
def select_domain(
    data: DomainSelect,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    domain = db.query(CareerDomain).filter(CareerDomain.id == data.domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Career domain not found.")
    current_user.selected_domain = domain.name
    db.commit()
    return {"message": "Career domain selected.", "domain": domain.name}


@router.get("/roadmap")
def get_roadmap(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    domain = db.query(CareerDomain).filter(CareerDomain.name == current_user.selected_domain).first()
    if not domain:
        domain = db.query(CareerDomain).order_by(CareerDomain.id).first()
    if not domain:
        return {"domain": None, "steps": []}

    steps = db.query(RoadmapStep).filter(RoadmapStep.domain_id == domain.id).order_by(RoadmapStep.step_order).all()
    progress_rows = db.query(StudentRoadmapProgress).filter(
        StudentRoadmapProgress.user_id == current_user.id,
        StudentRoadmapProgress.domain_id == domain.id,
    ).all()
    progress_by_step = {p.step_id: p.status for p in progress_rows}

    return {
        "domain": {
            "id": domain.id,
            "name": domain.name,
            "description": domain.description,
            "growth_rate_percent": domain.growth_rate_percent,
            "avg_salary_range": domain.avg_salary_range,
        },
        "steps": [
            {
                "id": s.id,
                "step_order": s.step_order,
                "skill_name": s.skill_name,
                "description": s.description,
                "resources": s.resources_json or [],
                "status": progress_by_step.get(s.id, "not_started"),
            }
            for s in steps
        ],
    }


@router.patch("/roadmap/{step_id}")
def update_roadmap_step(
    step_id: int,
    data: RoadmapStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.status not in ("not_started", "in_progress", "completed"):
        raise HTTPException(status_code=422, detail="Invalid roadmap status.")
    step = db.query(RoadmapStep).filter(RoadmapStep.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Roadmap step not found.")

    progress = db.query(StudentRoadmapProgress).filter(
        StudentRoadmapProgress.user_id == current_user.id,
        StudentRoadmapProgress.step_id == step_id,
    ).first()
    if not progress:
        progress = StudentRoadmapProgress(
            user_id=current_user.id,
            domain_id=step.domain_id,
            step_id=step_id,
            status=data.status,
        )
        db.add(progress)
    else:
        progress.status = data.status
        progress.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Roadmap progress updated.", "status": data.status}


@router.get("/readiness")
def get_readiness(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = db.query(ReadinessConfig).first()
    if not config:
        config = ReadinessConfig()

    aptitude = category_average(db, current_user.id, ["aptitude"])
    logical = category_average(db, current_user.id, ["aptitude", "technical"])
    verbal = 0.0
    technical = category_average(db, current_user.id, ["technical", "academic"])
    mock_test = category_average(db, current_user.id, ["mock_test"])

    domain = db.query(CareerDomain).filter(CareerDomain.name == current_user.selected_domain).first()
    roadmap_score = 0.0
    if domain:
        steps = db.query(RoadmapStep).filter(RoadmapStep.domain_id == domain.id).all()
        if steps:
            completed = db.query(StudentRoadmapProgress).filter(
                StudentRoadmapProgress.user_id == current_user.id,
                StudentRoadmapProgress.domain_id == domain.id,
                StudentRoadmapProgress.status == "completed",
            ).count()
            roadmap_score = round(completed / len(steps) * 100, 1)

    category_scores = {
        "aptitude": aptitude,
        "logical": logical,
        "verbal": verbal,
        "technical": technical,
        "roadmap": roadmap_score,
        "mock_test": mock_test,
    }
    weights = {
        "aptitude": config.aptitude_weight,
        "logical": config.logical_weight,
        "verbal": config.verbal_weight,
        "technical": config.technical_weight,
        "roadmap": config.roadmap_weight,
        "mock_test": config.mock_test_weight,
    }
    overall = round(sum(category_scores[k] * weights[k] / 100 for k in weights), 1)

    return {
        "overall_score": overall,
        "category_scores": category_scores,
        "weights": weights,
        "selected_domain": current_user.selected_domain,
    }


@router.post("/readiness/record")
def record_readiness(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    readiness = get_readiness(current_user=current_user, db=db)
    snapshot = ReadinessHistory(
        user_id=current_user.id,
        overall_score=readiness["overall_score"],
        category_scores_json=readiness["category_scores"],
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return {"message": "Readiness snapshot recorded.", "snapshot_id": snapshot.id}
