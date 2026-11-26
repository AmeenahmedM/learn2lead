"""
admin.py — Learn2Lead Admin Control Center API
Provides complete administrator authentication, student account management,
student academic detail inspection/editing, and platform-wide student analytics:
  - Role-verified admin guard (`require_admin`)
  - Platform overview KPIs (`GET /api/admin/overview`)
  - Student directory (`GET /api/admin/users`)
  - Student profile & academic details view (`GET /api/admin/users/{user_id}`)
  - Student subject & task updates (`PUT/PATCH/DELETE` under `/api/admin/users/{user_id}/...`)
  - Create, update, suspend/activate, reset password, and delete student accounts
  - Self-service Admin registration (`POST /api/admin/register`)
  - Aggregated platform-wide student analytics (`GET /api/admin/analytics`)
"""
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Subject, StudyTask, Quiz, Question, QuizAttempt
from .. import auth_utils
from ..auth_utils import get_current_user

router = APIRouter(prefix="/api/admin", tags=["Admin Management"])


# ==============================================================================
# PYDANTIC REQUEST SCHEMAS
# ==============================================================================
class AdminUserCreate(BaseModel):
    full_name: str
    email: str
    password: str
    role: str = "student"
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = None


class AdminStudentSubjectUpdate(BaseModel):
    name: Optional[str] = None
    difficulty: Optional[str] = None
    target_hours_per_week: Optional[float] = None
    exam_deadline: Optional[str] = None


class AdminStudentTaskUpdate(BaseModel):
    title: Optional[str] = None
    scheduled_date: Optional[str] = None
    duration_mins: Optional[int] = None
    priority: Optional[str] = None
    status: Optional[str] = None


class AdminRegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    setup_code: Optional[str] = None


# ==============================================================================
# INTERNAL HELPERS (SCHEMA MIGRATION, PASSWORD HASHING & ADMIN ROLE GUARD)
# ==============================================================================
def ensure_user_admin_columns(db: Session) -> None:
    """Safely adds `role` and `is_active` columns to `users` if not already present."""
    try:
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'student'"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
        db.commit()
    except Exception:
        db.rollback()


def get_display_name(user: User) -> str:
    """Returns the user's full display name across possible model column names."""
    for attr in ("full_name", "name", "username"):
        val = getattr(user, attr, None)
        if val and str(val).strip():
            return str(val).strip()
    return (user.email or "User").split("@")[0]


def set_display_name(user: User, display_name: str) -> None:
    """Sets the user's display name on whichever name column exists on the User model."""
    clean_name = display_name.strip()
    if hasattr(user, "full_name"):
        setattr(user, "full_name", clean_name)
    if hasattr(user, "name"):
        setattr(user, "name", clean_name)


def set_user_password_hash(user: User, raw_password: str) -> None:
    """Hashes a plain-text password using auth_utils (with passlib fallback) and assigns it."""
    hashed = None
    for fn_name in ("hash_password", "get_password_hash", "create_password_hash"):
        fn = getattr(auth_utils, fn_name, None)
        if callable(fn):
            hashed = fn(raw_password)
            break

    if not hashed:
        from passlib.context import CryptContext
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed = pwd_ctx.hash(raw_password)

    for attr in ("hashed_password", "password_hash", "password"):
        if hasattr(user, attr):
            setattr(user, attr, hashed)
            return


def get_user_meta_map(db: Session) -> dict[int, dict]:
    """Builds a map of {user_id: {'role': 'admin'|'student', 'is_active': bool}}."""
    ensure_user_admin_columns(db)
    admin_emails = {
        e.strip().lower()
        for e in os.getenv("ADMIN_EMAILS", "").split(",")
        if e.strip()
    }

    meta_map: dict[int, dict] = {}
    try:
        rows = db.execute(text("SELECT id, email, role, is_active FROM users")).fetchall()
        for row in rows:
            uid = int(row[0])
            email = str(row[1] or "").strip().lower()
            db_role = str(row[2] or "student").strip().lower()
            db_active = True if row[3] is None else bool(row[3])
            is_admin = (
                db_role == "admin"
                or uid == 1
                or email in admin_emails
                or email.startswith("admin@")
            )
            meta_map[uid] = {
                "role": "admin" if is_admin else "student",
                "is_active": db_active,
            }
    except Exception:
        db.rollback()
        for u in db.query(User).all():
            email = str(u.email or "").strip().lower()
            db_role = str(getattr(u, "role", "student") or "student").strip().lower()
            is_admin = (
                db_role == "admin"
                or bool(getattr(u, "is_admin", False))
                or u.id == 1
                or email in admin_emails
                or email.startswith("admin@")
            )
            meta_map[u.id] = {
                "role": "admin" if is_admin else "student",
                "is_active": bool(getattr(u, "is_active", True)),
            }

    return meta_map


def require_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency that ensures the authenticated caller is an active Administrator."""
    meta_map = get_user_meta_map(db)
    meta = meta_map.get(current_user.id, {"role": "student", "is_active": True})

    if not meta["is_active"]:
        raise HTTPException(
            status_code=403,
            detail="Your administrator account is currently suspended.",
        )

    if meta["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator privileges are required to access the Admin Control Center.",
        )

    return current_user


# ==============================================================================
# 1. PLATFORM OVERVIEW KPIS
# ==============================================================================
@router.get("/overview")
def get_admin_overview(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).all()
    meta_map = get_user_meta_map(db)

    student_users = [
        u for u in users
        if meta_map.get(u.id, {"role": "student"})["role"] != "admin"
    ]
    admin_users = [
        u for u in users
        if meta_map.get(u.id, {"role": "student"})["role"] == "admin"
    ]

    active_students = sum(
        1 for u in student_users
        if meta_map.get(u.id, {"is_active": True})["is_active"]
    )
    suspended_students = len(student_users) - active_students

    total_quizzes = db.query(Quiz).count()
    attempts = db.query(QuizAttempt).all()
    total_attempts = len(attempts)
    platform_avg_score = (
        round(sum(a.score_percent for a in attempts) / total_attempts, 1)
        if total_attempts else 0.0
    )

    tasks = db.query(StudyTask).all()
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.status == "completed")

    return {
        "current_admin": {
            "id": admin_user.id,
            "full_name": get_display_name(admin_user),
            "email": admin_user.email,
        },
        "total_users": len(users),
        "student_count": len(student_users),
        "admin_count": len(admin_users),
        "active_users": active_students,
        "suspended_users": suspended_students,
        "total_quizzes": total_quizzes,
        "total_attempts": total_attempts,
        "platform_avg_score": platform_avg_score,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
    }


# ==============================================================================
# 2. LIST ALL STUDENT ACCOUNTS (EXCLUDING ADMIN ACCOUNTS)
# ==============================================================================
@router.get("/users")
def list_all_users(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.id.desc()).all()
    meta_map = get_user_meta_map(db)

    subjects_by_user: dict[int, int] = {}
    for s in db.query(Subject).all():
        if s.user_id is not None:
            subjects_by_user[s.user_id] = subjects_by_user.get(s.user_id, 0) + 1

    tasks_by_user: dict[int, list[StudyTask]] = {}
    for t in db.query(StudyTask).all():
        tasks_by_user.setdefault(t.user_id, []).append(t)

    attempts_by_user: dict[int, list[QuizAttempt]] = {}
    for a in db.query(QuizAttempt).all():
        attempts_by_user.setdefault(a.user_id, []).append(a)

    result = []
    for u in users:
        meta = meta_map.get(u.id, {"role": "student", "is_active": True})
        if meta["role"] == "admin":
            continue

        u_tasks = tasks_by_user.get(u.id, [])
        u_attempts = attempts_by_user.get(u.id, [])
        avg_score = (
            round(sum(a.score_percent for a in u_attempts) / len(u_attempts), 1)
            if u_attempts else None
        )

        result.append({
            "id": u.id,
            "full_name": get_display_name(u),
            "email": u.email,
            "role": "student",
            "is_active": meta["is_active"],
            "subjects_count": subjects_by_user.get(u.id, 0),
            "tasks_count": len(u_tasks),
            "completed_tasks_count": sum(1 for t in u_tasks if t.status == "completed"),
            "quizzes_attempted": len(u_attempts),
            "avg_score": avg_score,
        })

    return result


# ==============================================================================
# 3. INSPECT & VIEW FULL STUDENT PROFILE + ACADEMIC DETAILS
# ==============================================================================
@router.get("/users/{user_id}")
def get_user_detail(
    user_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    meta_map = get_user_meta_map(db)
    m = meta_map.get(user.id, {"role": "student", "is_active": True})

    subjects = db.query(Subject).filter(Subject.user_id == user.id).order_by(Subject.id.desc()).all()
    all_tasks = (
        db.query(StudyTask)
        .filter(StudyTask.user_id == user.id)
        .order_by(StudyTask.scheduled_date.desc(), StudyTask.id.desc())
        .all()
    )
    all_attempts = (
        db.query(QuizAttempt, Quiz)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(QuizAttempt.user_id == user.id)
        .order_by(QuizAttempt.completed_at.desc())
        .all()
    )

    completed_tasks_count = sum(1 for t in all_tasks if t.status == "completed")
    completed_study_hours = round(
        sum(t.duration_mins for t in all_tasks if t.status == "completed") / 60.0, 1
    )
    avg_score = (
        round(sum(att.score_percent for att, _ in all_attempts) / len(all_attempts), 1)
        if all_attempts else None
    )
    created_val = getattr(user, "created_at", None)
    created_str = created_val.strftime("%Y-%m-%d") if hasattr(created_val, "strftime") else "Registered"

    return {
        "id": user.id,
        "full_name": get_display_name(user),
        "email": user.email,
        "role": m["role"],
        "is_active": m["is_active"],
        "created_at": created_str,
        "avg_score": avg_score,
        "quizzes_attempted": len(all_attempts),
        "tasks_count": len(all_tasks),
        "completed_tasks_count": completed_tasks_count,
        "completed_study_hours": completed_study_hours,
        "subjects": [
            {
                "id": s.id,
                "name": s.name,
                "difficulty": s.difficulty,
                "target_hours_per_week": s.target_hours_per_week,
                "exam_deadline": s.exam_deadline,
            }
            for s in subjects
        ],
        "recent_tasks": [
            {
                "id": t.id,
                "title": t.title,
                "scheduled_date": t.scheduled_date,
                "duration_mins": t.duration_mins,
                "priority": t.priority,
                "status": t.status,
            }
            for t in all_tasks[:25]
        ],
        "recent_attempts": [
            {
                "attempt_id": att.id,
                "quiz_title": q.title,
                "subject": q.subject_or_domain,
                "score_percent": att.score_percent,
                "weak_topics": att.weak_topics_json or [],
                "completed_at": att.completed_at.strftime("%Y-%m-%d %H:%M"),
            }
            for att, q in all_attempts[:25]
        ],
    }


# ==============================================================================
# 3B. ADMIN UPDATE / REMOVE STUDENT SUBJECTS & STUDY TASKS
# ==============================================================================
@router.put("/users/{user_id}/subjects/{subject_id}")
def admin_update_student_subject(
    user_id: int,
    subject_id: int,
    data: AdminStudentSubjectUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    subj = db.query(Subject).filter(Subject.id == subject_id, Subject.user_id == user_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Student subject not found.")
    if data.name is not None and data.name.strip():
        subj.name = data.name.strip()
    if data.difficulty is not None and data.difficulty.strip():
        subj.difficulty = data.difficulty.strip()
    if data.target_hours_per_week is not None:
        subj.target_hours_per_week = float(data.target_hours_per_week)
    if data.exam_deadline is not None:
        subj.exam_deadline = data.exam_deadline.strip() or None
    db.commit()
    return {"message": f"Updated subject '{subj.name}'."}


@router.delete("/users/{user_id}/subjects/{subject_id}")
def admin_delete_student_subject(
    user_id: int,
    subject_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    subj = db.query(Subject).filter(Subject.id == subject_id, Subject.user_id == user_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Student subject not found.")
    db.query(StudyTask).filter(StudyTask.subject_id == subject_id).update({"subject_id": None})
    db.delete(subj)
    db.commit()
    return {"message": "Subject removed from student profile."}


@router.patch("/users/{user_id}/tasks/{task_id}")
def admin_update_student_task(
    user_id: int,
    task_id: int,
    data: AdminStudentTaskUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    task = db.query(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Student study task not found.")
    if data.title is not None and data.title.strip():
        task.title = data.title.strip()
    if data.scheduled_date is not None and data.scheduled_date.strip():
        task.scheduled_date = data.scheduled_date.strip()
    if data.duration_mins is not None:
        task.duration_mins = int(data.duration_mins)
    if data.priority is not None and data.priority.strip():
        task.priority = data.priority.strip()
    if data.status is not None:
        if data.status not in ("pending", "completed", "missed"):
            raise HTTPException(status_code=400, detail="Invalid task status.")
        task.status = data.status
    db.commit()
    return {"message": "Student study task updated."}


@router.delete("/users/{user_id}/tasks/{task_id}")
def admin_delete_student_task(
    user_id: int,
    task_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    task = db.query(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Student study task not found.")
    db.delete(task)
    db.commit()
    return {"message": "Study task deleted."}


# ==============================================================================
# 4. CREATE NEW USER ACCOUNT (ADMIN ACTION)
# ==============================================================================
@router.post("/users")
def create_user_by_admin(
    data: AdminUserCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    email_clean = data.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    role_clean = "admin" if data.role.strip().lower() == "admin" else "student"

    new_user = User(email=email_clean)
    set_display_name(new_user, data.full_name or email_clean.split("@")[0])
    set_user_password_hash(new_user, data.password)
    if hasattr(new_user, "role"):
        setattr(new_user, "role", role_clean)
    if hasattr(new_user, "is_admin"):
        setattr(new_user, "is_admin", role_clean == "admin")
    if hasattr(new_user, "is_active"):
        setattr(new_user, "is_active", bool(data.is_active))

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    ensure_user_admin_columns(db)
    try:
        db.execute(
            text("UPDATE users SET role = :role, is_active = :active WHERE id = :uid"),
            {"role": role_clean, "active": bool(data.is_active), "uid": new_user.id},
        )
        db.commit()
    except Exception:
        db.rollback()

    return {
        "message": f"Account created for {get_display_name(new_user)} ({role_clean}).",
        "id": new_user.id,
    }


# ==============================================================================
# 5. UPDATE USER PROFILE, ROLE, STATUS OR RESET PASSWORD
# ==============================================================================
@router.put("/users/{user_id}")
def update_user_by_admin(
    user_id: int,
    data: AdminUserUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    if data.full_name is not None and data.full_name.strip():
        set_display_name(user, data.full_name.strip())

    if data.email is not None and data.email.strip():
        new_email = data.email.strip().lower()
        if "@" not in new_email:
            raise HTTPException(status_code=400, detail="Invalid email address.")
        duplicate = db.query(User).filter(User.email == new_email, User.id != user.id).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="Another account already uses this email.")
        user.email = new_email

    if data.new_password is not None and data.new_password.strip():
        if len(data.new_password.strip()) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
        set_user_password_hash(user, data.new_password.strip())

    ensure_user_admin_columns(db)
    meta_map = get_user_meta_map(db)
    current_meta = meta_map.get(user.id, {"role": "student", "is_active": True})

    next_role = current_meta["role"]
    if data.role is not None:
        requested_role = "admin" if data.role.strip().lower() == "admin" else "student"
        if user.id == admin_user.id and requested_role != "admin":
            raise HTTPException(status_code=400, detail="You cannot remove your own Admin privileges.")
        next_role = requested_role
        if hasattr(user, "role"):
            setattr(user, "role", next_role)
        if hasattr(user, "is_admin"):
            setattr(user, "is_admin", next_role == "admin")

    next_active = current_meta["is_active"]
    if data.is_active is not None:
        if user.id == admin_user.id and not data.is_active:
            raise HTTPException(status_code=400, detail="You cannot suspend your own Admin account.")
        next_active = bool(data.is_active)
        if hasattr(user, "is_active"):
            setattr(user, "is_active", next_active)

    db.commit()

    try:
        db.execute(
            text("UPDATE users SET role = :role, is_active = :active WHERE id = :uid"),
            {"role": next_role, "active": next_active, "uid": user.id},
        )
        db.commit()
    except Exception:
        db.rollback()

    return {"message": f"Updated account for {get_display_name(user)}."}


# ==============================================================================
# 6. DELETE USER ACCOUNT (WITH SAFE CASCADE CLEANUP)
# ==============================================================================
@router.delete("/users/{user_id}")
def delete_user_by_admin(
    user_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own currently signed-in Admin account.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    display_name = get_display_name(user)

    db.query(QuizAttempt).filter(QuizAttempt.user_id == user.id).delete()

    user_quiz_ids = [q.id for q in db.query(Quiz).filter(Quiz.created_by == user.id).all()]
    if user_quiz_ids:
        db.query(QuizAttempt).filter(QuizAttempt.quiz_id.in_(user_quiz_ids)).delete(synchronize_session=False)
        db.query(Question).filter(Question.quiz_id.in_(user_quiz_ids)).delete(synchronize_session=False)
        db.query(Quiz).filter(Quiz.id.in_(user_quiz_ids)).delete(synchronize_session=False)

    db.query(StudyTask).filter(StudyTask.user_id == user.id).delete()
    db.query(Subject).filter(Subject.user_id == user.id).delete()

    db.delete(user)
    db.commit()

    return {"message": f"Deleted user account '{display_name}' and all associated records."}


# ==============================================================================
# 7. SELF-SERVICE ADMIN ACCOUNT REGISTRATION (ADMIN PORTAL)
# ==============================================================================
@router.post("/register")
def register_admin_account(
    data: AdminRegisterRequest,
    db: Session = Depends(get_db),
):
    """Creates a new Administrator account from the dedicated Admin Portal."""
    required_setup_key = os.getenv("ADMIN_SETUP_KEY", "").strip()
    if required_setup_key and (data.setup_code or "").strip() != required_setup_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid Admin Setup Code. Check ADMIN_SETUP_KEY in your .env file.",
        )

    email_clean = data.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists. Please sign in instead.",
        )

    display_name = (data.full_name or "").strip() or email_clean.split("@")[0]

    new_admin = User(email=email_clean)
    set_display_name(new_admin, display_name)
    set_user_password_hash(new_admin, data.password)
    if hasattr(new_admin, "role"):
        setattr(new_admin, "role", "admin")
    if hasattr(new_admin, "is_admin"):
        setattr(new_admin, "is_admin", True)
    if hasattr(new_admin, "is_active"):
        setattr(new_admin, "is_active", True)

    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    ensure_user_admin_columns(db)
    try:
        db.execute(
            text("UPDATE users SET role = 'admin', is_active = TRUE WHERE id = :uid"),
            {"uid": new_admin.id},
        )
        db.commit()
    except Exception:
        db.rollback()

    return {
        "message": f"Admin account created for {display_name}!",
        "id": new_admin.id,
        "email": email_clean,
        "role": "admin",
    }


# ==============================================================================
# 8. PLATFORM-WIDE STUDENT ANALYTICS (AGGREGATED ACROSS ALL STUDENTS)
# ==============================================================================
@router.get("/analytics")
def get_platform_student_analytics(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Aggregates quiz scores, weak topics, study tasks, and student rankings across the entire platform."""
    users = db.query(User).all()
    meta_map = get_user_meta_map(db)

    student_users = [
        u for u in users
        if meta_map.get(u.id, {"role": "student"})["role"] != "admin"
    ]
    student_ids = {u.id for u in student_users}
    user_name_map = {u.id: get_display_name(u) for u in users}
    user_email_map = {u.id: u.email for u in users}

    all_attempt_rows = (
        db.query(QuizAttempt, Quiz)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .order_by(QuizAttempt.completed_at.asc())
        .all()
    )

    attempt_rows = (
        [(att, q) for att, q in all_attempt_rows if att.user_id in student_ids]
        if student_ids else all_attempt_rows
    )

    subject_scores: dict[str, list[float]] = {}
    daily_scores: dict[str, list[float]] = {}
    weak_topic_counts: dict[str, int] = {}
    per_student_scores: dict[int, list[float]] = {}
    score_buckets = {"high": 0, "medium": 0, "low": 0}

    for att, q in attempt_rows:
        subj = (q.subject_or_domain or "General").strip()
        subject_scores.setdefault(subj, []).append(att.score_percent)

        day_label = att.completed_at.strftime("%Y-%m-%d")
        daily_scores.setdefault(day_label, []).append(att.score_percent)

        per_student_scores.setdefault(att.user_id, []).append(att.score_percent)

        if att.score_percent >= 75:
            score_buckets["high"] += 1
        elif att.score_percent >= 60:
            score_buckets["medium"] += 1
        else:
            score_buckets["low"] += 1

        for wt in (att.weak_topics_json or []):
            tag = str(wt).strip()
            if tag:
                weak_topic_counts[tag] = weak_topic_counts.get(tag, 0) + 1

    subject_averages = sorted(
        [
            {
                "subject": subj,
                "avg_score": round(sum(vals) / len(vals), 1),
                "attempts": len(vals),
            }
            for subj, vals in subject_scores.items()
        ],
        key=lambda x: x["attempts"],
        reverse=True,
    )[:10]

    timeline = [
        {
            "date": day,
            "avg_score": round(sum(vals) / len(vals), 1),
            "attempts": len(vals),
        }
        for day, vals in sorted(daily_scores.items())[-14:]
    ]

    top_weak_topics = [
        {"topic": topic, "count": cnt}
        for topic, cnt in sorted(weak_topic_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    all_tasks = db.query(StudyTask).all()
    student_tasks = (
        [t for t in all_tasks if t.user_id in student_ids]
        if student_ids else all_tasks
    )
    completed_tasks = sum(1 for t in student_tasks if t.status == "completed")
    pending_tasks = sum(1 for t in student_tasks if t.status == "pending")
    missed_tasks = sum(1 for t in student_tasks if t.status == "missed")
    total_study_hours = round(
        sum(t.duration_mins for t in student_tasks if t.status == "completed") / 60.0, 1
    )

    leaderboard = sorted(
        [
            {
                "user_id": uid,
                "full_name": user_name_map.get(uid, f"Student #{uid}"),
                "email": user_email_map.get(uid, ""),
                "avg_score": round(sum(scores) / len(scores), 1),
                "attempts": len(scores),
            }
            for uid, scores in per_student_scores.items()
        ],
        key=lambda x: (x["avg_score"], x["attempts"]),
        reverse=True,
    )[:5]

    return {
        "total_students": len(student_users),
        "total_student_attempts": len(attempt_rows),
        "total_completed_study_hours": total_study_hours,
        "subject_averages": subject_averages,
        "timeline": timeline,
        "score_distribution": score_buckets,
        "task_breakdown": {
            "completed": completed_tasks,
            "pending": pending_tasks,
            "missed": missed_tasks,
        },
        "top_weak_topics": top_weak_topics,
        "top_students": leaderboard,
    }