"""
academics.py — MODULE 1 (Member 1): Academic Study Management
Includes REAL Gemini AI 15-Question Quiz Generation with Privacy Guard:
  - Option 1: AI-Generated 15 Technical MCQs from any Scheduled Subject & Topic
  - Option 2: 15 MCQs generated strictly from Uploaded Study Notes (PDF / TXT)
"""
import io
import json
import os
import re
import time
from pathlib import Path
from typing import Optional, Dict, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Subject, StudyTask, Quiz, Question, QuizAttempt
from ..auth_utils import get_current_user

router = APIRouter(prefix="/api/academics", tags=["Module 1: Academics"])


# ==============================================================================
# PYDANTIC SCHEMAS
# ==============================================================================
class SubjectCreate(BaseModel):
    name: str
    difficulty: str = "Medium"
    target_hours_per_week: float = 5.0
    exam_deadline: Optional[str] = None


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    difficulty: Optional[str] = None
    target_hours_per_week: Optional[float] = None
    exam_deadline: Optional[str] = None


class TaskCreate(BaseModel):
    subject_id: Optional[int] = None
    title: str
    scheduled_date: str
    duration_mins: int = 45
    priority: str = "Medium"


class TaskStatusUpdate(BaseModel):
    status: str


class QuizSubmitRequest(BaseModel):
    answers: Dict[str, str]


# ==============================================================================
# AI HELPERS: Load API Key Safely, Extract Notes, Privacy Guard, Generate MCQs
# ==============================================================================
def load_gemini_api_key() -> tuple[str, str]:
    """Reloads GEMINI_API_KEY from .env files and returns (api_key, debug_info)."""
    resolved = Path(__file__).resolve()
    candidate_paths = []
    for parent_idx in (1, 2, 3):
        if parent_idx < len(resolved.parents):
            candidate_paths.append(resolved.parents[parent_idx] / ".env")
    candidate_paths.append(Path.cwd() / ".env")

    # Deduplicate while preserving order
    unique_paths = list(dict.fromkeys(candidate_paths))
    checked_info = []

    for env_path in unique_paths:
        if not env_path.exists():
            continue
        found_keys = []
        try:
            # utf-8-sig automatically strips Windows UTF-8 BOM characters
            for raw_line in env_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                key_name = k.strip().upper()
                found_keys.append(key_name)
                if key_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                    cleaned_val = v.strip().strip('"').strip("'")
                    if cleaned_val:
                        os.environ["GEMINI_API_KEY"] = cleaned_val
                        return cleaned_val, str(env_path)
        except OSError:
            pass
        checked_info.append(f"{env_path} (keys found: {', '.join(found_keys) or 'none'})")

    env_val = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip().strip('"').strip("'")
    if env_val:
        return env_val, "os.environ"

    debug_msg = " | ".join(checked_info) if checked_info else f"No .env file found in {[str(p) for p in unique_paths]}"
    return "", debug_msg


def extract_text_from_upload(file_bytes: bytes, filename: str) -> str:
    """Extracts plain text from uploaded .pdf or .txt study notes."""
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Please install pypdf first: pip install pypdf",
            )
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages_text).strip()
    return file_bytes.decode("utf-8", errors="ignore").strip()


def sanitize_for_ai(text: str) -> str:
    """Privacy Guard: Strips emails and phone numbers before sending text to Gemini AI.
    User profile, name, email, ID, schedules, and quiz scores are NEVER passed to Gemini."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[REDACTED_EMAIL]", text)
    text = re.sub(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b", "[REDACTED_PHONE]", text)
    return text.strip()


def generate_mcqs_with_gemini(
    subject_name: str,
    topic_name: str,
    mode: str,
    notes_text: str = "",
    num_questions: int = 15,
) -> List[dict]:
    """Generates technical MCQs via Gemini API for either a topic or uploaded notes."""
    api_key, debug_info = load_gemini_api_key()
    if not api_key or api_key == "PASTE_YOUR_GEMINI_API_KEY_HERE" or "your_key" in api_key.lower():
        raise HTTPException(
            status_code=400,
            detail=f"GEMINI_API_KEY not detected. Checked: {debug_info}",
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Please install google-genai first: pip install google-genai",
        )

    subject_name = sanitize_for_ai(subject_name)
    topic_name = sanitize_for_ai(topic_name)

    if mode == "upload_notes":
        trimmed_notes = sanitize_for_ai(notes_text)[:18000]
        prompt = f"""You are a university computer science and engineering professor.
Generate EXACTLY {num_questions} technical multiple-choice questions (MCQs) STRICTLY based on the student's uploaded study notes below for Subject: "{subject_name}", Topic: "{topic_name}".

Rules:
- Every question must test real concepts, definitions, syntax, or problem-solving directly from the notes.
- Do NOT write generic study-habit questions.
- Provide exactly 4 clear answer options per question.
- "correct_answer" MUST match one of the 4 strings in "options" character-for-character.
- Return ONLY a valid JSON array of {num_questions} objects with keys:
  "question_text", "options" (list of 4 strings), "correct_answer", "topic_tag", "explanation".

STUDENT STUDY NOTES:
\"\"\"
{trimmed_notes}
\"\"\"
"""
    else:
        prompt = f"""You are a university computer science and engineering professor.
Generate EXACTLY {num_questions} technical, exam-grade multiple-choice questions (MCQs) specifically for:
- Subject: "{subject_name}"
- Topic: "{topic_name}"

Rules:
- Every single question must test real technical knowledge, syntax, architecture, or practical concepts of "{topic_name}" in "{subject_name}" (mix of easy, medium, and applied questions).
- Do NOT write generic study-habit or meta-learning questions.
- Provide exactly 4 clear answer options per question.
- "correct_answer" MUST match one of the 4 strings in "options" character-for-character.
- Return ONLY a valid JSON array of {num_questions} objects with keys:
  "question_text", "options" (list of 4 strings), "correct_answer", "topic_tag", "explanation".
"""

    client = genai.Client(api_key=api_key)

    # Start with gemini-3.8-flash and dynamically discover any other active Gemini text models
    candidate_models = ["gemini-3.8-flash"]
    try:
        for m in client.models.list():
            m_name = (getattr(m, "name", "") or "").replace("models/", "")
            supported = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None) or []
            if (
                m_name.startswith("gemini-")
                and "2.5" not in m_name
                and "embedding" not in m_name
                and "imagen" not in m_name
                and "veo" not in m_name
                and "tts" not in m_name
                and "audio" not in m_name
                and m_name not in candidate_models
                and (not supported or any("generateContent" in str(a) for a in supported))
            ):
                candidate_models.append(m_name)
    except Exception:
        # Fallback list if model listing is unavailable
        for fallback in ("gemini-3.8-flash-lite", "gemini-3.0-flash", "gemini-2.0-flash"):
            if fallback not in candidate_models:
                candidate_models.append(fallback)

    response = None
    last_exc = None
    transient_exc = None

    try:
        for model_name in candidate_models:
            # Retry up to 3 times on temporary 503 high-demand spikes before trying the next model
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.4,
                        ),
                    )
                    break
                except Exception as model_exc:
                    err_msg = str(model_exc).upper()
                    # Model not found for this account -> skip to next available model immediately
                    if "404" in err_msg or "NOT_FOUND" in err_msg:
                        last_exc = model_exc
                        break
                    # Temporary high demand or rate limit -> wait briefly and retry, then try next model
                    if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg or "OVERLOADED" in err_msg:
                        transient_exc = model_exc
                        if attempt < 2:
                            time.sleep(2 * (attempt + 1))
                            continue
                        break
                    raise
            if response is not None:
                break

        if response is None:
            if transient_exc is not None:
                raise RuntimeError(
                    "Gemini AI servers are momentarily busy (503). Please wait 10 seconds and click Generate again."
                )
            raise last_exc or RuntimeError("No supported Gemini model was available for your API key.")

        raw_text = (response.text or "").strip()
        fence = "`" * 3
        if raw_text.startswith(fence):
            raw_text = raw_text.strip("`").replace("json\n", "", 1).strip()
        questions = json.loads(raw_text)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini AI quiz generation failed: {str(exc)}",
        )

    if not isinstance(questions, list) or len(questions) == 0:
        raise HTTPException(status_code=502, detail="Gemini AI returned an empty question list. Please try again.")

    cleaned = []
    for item in questions[:num_questions]:
        opts = item.get("options", [])
        ans = str(item.get("correct_answer", "")).strip()
        if not item.get("question_text") or not isinstance(opts, list) or len(opts) < 2:
            continue
        if ans not in opts:
            ans = str(opts[0])
        cleaned.append({
            "question_text": str(item["question_text"]).strip(),
            "options": [str(o).strip() for o in opts[:4]],
            "correct_answer": ans,
            "topic_tag": str(item.get("topic_tag") or topic_name)[:100],
            "explanation": str(item.get("explanation") or "").strip(),
        })
    return cleaned


# ==============================================================================
# A. PERSONALIZED STUDY PLANNER — SUBJECTS CRUD
# ==============================================================================
@router.get("/subjects")
def list_subjects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subjects = (
        db.query(Subject)
        .filter((Subject.user_id == current_user.id) | (Subject.is_global == True))
        .order_by(Subject.id.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "name": s.name,
            "difficulty": s.difficulty,
            "target_hours_per_week": s.target_hours_per_week,
            "exam_deadline": s.exam_deadline,
            "is_global": s.is_global,
        }
        for s in subjects
    ]


@router.post("/subjects")
def create_subject(
    data: SubjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subj = Subject(
        user_id=current_user.id,
        name=data.name.strip(),
        difficulty=data.difficulty,
        target_hours_per_week=data.target_hours_per_week,
        exam_deadline=data.exam_deadline or None,
        is_global=False,
    )
    db.add(subj)
    db.commit()
    db.refresh(subj)
    return {"message": "Subject added!", "id": subj.id, "name": subj.name}


@router.put("/subjects/{subject_id}")
def update_subject(
    subject_id: int,
    data: SubjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subj = db.query(Subject).filter(Subject.id == subject_id, Subject.user_id == current_user.id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found.")
    if data.name is not None:
        subj.name = data.name.strip()
    if data.difficulty is not None:
        subj.difficulty = data.difficulty
    if data.target_hours_per_week is not None:
        subj.target_hours_per_week = data.target_hours_per_week
    if data.exam_deadline is not None:
        subj.exam_deadline = data.exam_deadline or None
    db.commit()
    return {"message": "Subject updated!"}


@router.delete("/subjects/{subject_id}")
def delete_subject(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subj = db.query(Subject).filter(Subject.id == subject_id, Subject.user_id == current_user.id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found.")
    db.query(StudyTask).filter(StudyTask.subject_id == subject_id).update({"subject_id": None})
    db.delete(subj)
    db.commit()
    return {"message": "Subject deleted."}


# ==============================================================================
# A2. PERSONALIZED STUDY PLANNER — STUDY TASKS CRUD
# ==============================================================================
@router.get("/tasks")
def list_tasks(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(StudyTask).filter(StudyTask.user_id == current_user.id)
    if status and status != "all":
        query = query.filter(StudyTask.status == status)
    tasks = query.order_by(StudyTask.scheduled_date.asc(), StudyTask.id.desc()).all()

    subj_map = {
        s.id: s.name
        for s in db.query(Subject).filter((Subject.user_id == current_user.id) | (Subject.is_global == True)).all()
    }

    return [
        {
            "id": t.id,
            "subject_id": t.subject_id,
            "subject_name": subj_map.get(t.subject_id, "General Study"),
            "title": t.title,
            "scheduled_date": t.scheduled_date,
            "duration_mins": t.duration_mins,
            "priority": t.priority,
            "status": t.status,
        }
        for t in tasks
    ]


@router.post("/tasks")
def create_task(
    data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = StudyTask(
        user_id=current_user.id,
        subject_id=data.subject_id,
        title=data.title.strip(),
        scheduled_date=data.scheduled_date,
        duration_mins=data.duration_mins,
        priority=data.priority,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"message": "Study task scheduled!", "id": task.id}


@router.patch("/tasks/{task_id}")
def update_task_status(
    task_id: int,
    data: TaskStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Study task not found.")
    if data.status not in ("pending", "completed", "missed"):
        raise HTTPException(status_code=400, detail="Invalid status.")
    task.status = data.status
    db.commit()
    return {"message": f"Task marked as {data.status}."}


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Study task not found.")
    db.delete(task)
    db.commit()
    return {"message": "Study task deleted."}


# ==============================================================================
# B. AI-GENERATED & NOTES-BASED SUBJECT QUIZZES (15 MCQs)
# ==============================================================================
@router.post("/quizzes/generate")
async def generate_quiz(
    subject_name: str = Form(...),
    topic_name: str = Form(...),
    mode: str = Form("ai_topic"),              # "ai_topic" | "upload_notes"
    num_questions: int = Form(15),
    pasted_notes: str = Form(""),
    notes_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generates 15 real technical MCQs using Gemini AI from either the scheduled topic OR uploaded notes."""
    num_questions = max(5, min(num_questions, 25))
    notes_text = pasted_notes.strip()

    if mode == "upload_notes":
        if notes_file and notes_file.filename:
            file_bytes = await notes_file.read()
            extracted = extract_text_from_upload(file_bytes, notes_file.filename)
            notes_text = (extracted + "\n" + notes_text).strip()
        if len(notes_text) < 40:
            raise HTTPException(
                status_code=400,
                detail="Please upload a PDF/TXT notes file or paste at least a few lines of study notes.",
            )

    mcqs = generate_mcqs_with_gemini(
        subject_name=subject_name.strip(),
        topic_name=topic_name.strip(),
        mode=mode,
        notes_text=notes_text,
        num_questions=num_questions,
    )

    label = "Notes Quiz" if mode == "upload_notes" else "AI Quiz"
    quiz = Quiz(
        category="academic",
        subject_or_domain=subject_name.strip(),
        topic=topic_name.strip(),
        title=f"{subject_name.strip()}: {topic_name.strip()} ({label})",
        duration_mins=max(10, len(mcqs)),
        created_by=current_user.id,
    )
    db.add(quiz)
    db.flush()

    for q in mcqs:
        db.add(Question(
            quiz_id=quiz.id,
            question_text=q["question_text"],
            question_type="mcq",
            options_json=q["options"],
            correct_answer=q["correct_answer"],
            topic_tag=q["topic_tag"],
            explanation=q["explanation"],
        ))
    db.commit()
    db.refresh(quiz)

    return {
        "message": f"Generated {len(mcqs)} questions successfully!",
        "quiz_id": quiz.id,
        "title": quiz.title,
        "question_count": len(mcqs),
    }


@router.get("/quizzes")
def list_academic_quizzes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns quizzes created by this student."""
    quizzes = (
        db.query(Quiz)
        .filter(Quiz.category == "academic", Quiz.created_by == current_user.id)
        .order_by(Quiz.id.desc())
        .all()
    )
    result = []
    for q in quizzes:
        q_count = db.query(Question).filter(Question.quiz_id == q.id).count()
        last_attempt = (
            db.query(QuizAttempt)
            .filter(QuizAttempt.user_id == current_user.id, QuizAttempt.quiz_id == q.id)
            .order_by(QuizAttempt.completed_at.desc())
            .first()
        )
        source_type = "From Notes" if "(Notes Quiz)" in q.title else "AI Generated"
        result.append({
            "id": q.id,
            "subject_or_domain": q.subject_or_domain,
            "topic": q.topic,
            "title": q.title,
            "source_type": source_type,
            "duration_mins": q.duration_mins,
            "question_count": q_count,
            "last_score": last_attempt.score_percent if last_attempt else None,
        })
    return result


@router.delete("/quizzes/{quiz_id}")
def delete_quiz(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.created_by == current_user.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz_id).delete()
    db.query(Question).filter(Question.quiz_id == quiz_id).delete()
    db.delete(quiz)
    db.commit()
    return {"message": "Quiz deleted."}


@router.get("/quizzes/{quiz_id}")
def get_quiz_questions(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    questions = db.query(Question).filter(Question.quiz_id == quiz_id).order_by(Question.id.asc()).all()
    return {
        "id": quiz.id,
        "title": quiz.title,
        "subject_or_domain": quiz.subject_or_domain,
        "topic": quiz.topic,
        "duration_mins": quiz.duration_mins,
        "questions": [
            {
                "id": item.id,
                "question_text": item.question_text,
                "question_type": item.question_type,
                "options": item.options_json or [],
                "topic_tag": item.topic_tag,
            }
            for item in questions
        ],
    }


@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(
    quiz_id: int,
    data: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    questions = db.query(Question).filter(Question.quiz_id == quiz_id).all()
    if not questions:
        raise HTTPException(status_code=400, detail="Quiz has no questions.")

    correct_count = 0
    weak_topics = []
    review = []

    for q in questions:
        selected = data.answers.get(str(q.id), "")
        is_correct = selected.strip().lower() == q.correct_answer.strip().lower()
        if is_correct:
            correct_count += 1
        elif q.topic_tag and q.topic_tag not in weak_topics:
            weak_topics.append(q.topic_tag)

        review.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "selected": selected or "(Not answered)",
            "correct_answer": q.correct_answer,
            "is_correct": is_correct,
            "topic_tag": q.topic_tag,
            "explanation": q.explanation,
        })

    score_percent = round((correct_count / len(questions)) * 100, 1)

    attempt = QuizAttempt(
        user_id=current_user.id,
        quiz_id=quiz.id,
        score_percent=score_percent,
        answers_json=data.answers,
        weak_topics_json=weak_topics,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "quiz_title": quiz.title,
        "score_percent": score_percent,
        "correct_count": correct_count,
        "total_questions": len(questions),
        "weak_topics": weak_topics,
        "review": review,
    }


@router.get("/quiz-history")
def get_quiz_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = (
        db.query(QuizAttempt, Quiz)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(QuizAttempt.user_id == current_user.id, Quiz.category == "academic")
        .order_by(QuizAttempt.completed_at.desc())
        .all()
    )
    return [
        {
            "attempt_id": att.id,
            "quiz_id": q.id,
            "quiz_title": q.title,
            "subject": q.subject_or_domain,
            "score_percent": att.score_percent,
            "weak_topics": att.weak_topics_json or [],
            "completed_at": att.completed_at.strftime("%Y-%m-%d %H:%M"),
        }
        for att, q in attempts
    ]


@router.get("/quiz-history/{attempt_id}")
def get_quiz_attempt_detail(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns full question-by-question review (user answer vs correct answer) for a past quiz attempt."""
    row = (
        db.query(QuizAttempt, Quiz)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(QuizAttempt.id == attempt_id, QuizAttempt.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")

    attempt, quiz = row
    questions = (
        db.query(Question)
        .filter(Question.quiz_id == quiz.id)
        .order_by(Question.id.asc())
        .all()
    )
    saved_answers = attempt.answers_json or {}
    if isinstance(saved_answers, str):
        try:
            saved_answers = json.loads(saved_answers)
        except Exception:
            saved_answers = {}

    correct_count = 0
    review = []
    for q in questions:
        selected = str(saved_answers.get(str(q.id), "") or "")
        is_correct = selected.strip().lower() == q.correct_answer.strip().lower()
        if is_correct:
            correct_count += 1
        review.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "selected": selected or "(Not answered)",
            "correct_answer": q.correct_answer,
            "is_correct": is_correct,
            "topic_tag": q.topic_tag,
            "explanation": q.explanation,
        })

    return {
        "attempt_id": attempt.id,
        "quiz_id": quiz.id,
        "quiz_title": quiz.title,
        "subject": quiz.subject_or_domain,
        "completed_at": attempt.completed_at.strftime("%Y-%m-%d %H:%M"),
        "score_percent": attempt.score_percent,
        "correct_count": correct_count,
        "total_questions": len(questions),
        "weak_topics": attempt.weak_topics_json or [],
        "review": review,
    }


# ==============================================================================
# C. ACADEMIC PERFORMANCE ANALYTICS
# ==============================================================================
@router.get("/analytics")
def get_academic_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = (
        db.query(QuizAttempt, Quiz)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(QuizAttempt.user_id == current_user.id, Quiz.category == "academic")
        .order_by(QuizAttempt.completed_at.asc())
        .all()
    )

    subject_scores_map: Dict[str, List[float]] = {}
    timeline = []
    weak_topic_counts: Dict[str, int] = {}

    for att, q in attempts:
        subject_scores_map.setdefault(q.subject_or_domain, []).append(att.score_percent)
        timeline.append({
            "label": f"{q.subject_or_domain[:14]} ({att.completed_at.strftime('%m/%d')})",
            "score": att.score_percent,
        })
        for wt in (att.weak_topics_json or []):
            weak_topic_counts[wt] = weak_topic_counts.get(wt, 0) + 1

    subject_averages = [
        {"subject": subj, "avg_score": round(sum(scores) / len(scores), 1), "attempts": len(scores)}
        for subj, scores in subject_scores_map.items()
    ]

    overall_avg = (
        round(sum(att.score_percent for att, _ in attempts) / len(attempts), 1)
        if attempts else 0.0
    )

    score_delta = None
    if len(attempts) >= 2:
        score_delta = round(attempts[-1][0].score_percent - attempts[-2][0].score_percent, 1)

    strong_subjects = [s["subject"] for s in subject_averages if s["avg_score"] >= 75]
    weak_subjects = [s["subject"] for s in subject_averages if s["avg_score"] < 65]
    top_weak_topics = sorted(weak_topic_counts.keys(), key=lambda k: weak_topic_counts[k], reverse=True)[:5]

    tasks = db.query(StudyTask).filter(StudyTask.user_id == current_user.id).all()
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.status == "completed")
    pending_tasks = sum(1 for t in tasks if t.status == "pending")
    missed_tasks = sum(1 for t in tasks if t.status == "missed")
    planned_hours = round(sum(t.duration_mins for t in tasks) / 60.0, 1)
    completed_hours = round(sum(t.duration_mins for t in tasks if t.status == "completed") / 60.0, 1)

    suggestions = []
    if not attempts:
        suggestions.append("Generate and complete a 15-question AI or Notes quiz to unlock insights.")
    if weak_subjects:
        suggestions.append(f"Prioritize extra revision blocks for: {', '.join(weak_subjects)} (average score below 65%).")
    if top_weak_topics:
        suggestions.append(f"Focus your next study session on weak quiz topics: {', '.join(top_weak_topics[:3])}.")
    if pending_tasks > 3:
        suggestions.append(f"You have {pending_tasks} pending study tasks—break them into 45-minute focused blocks.")
    if missed_tasks > 0:
        suggestions.append(f"Reschedule your {missed_tasks} missed study task(s) to stay on track for exam deadlines.")
    if strong_subjects and not weak_subjects:
        suggestions.append(f"Great momentum in {', '.join(strong_subjects)}! Move ahead to Employability prep.")

    return {
        "overall_avg_score": overall_avg,
        "total_attempts": len(attempts),
        "score_delta": score_delta,
        "subject_averages": subject_averages,
        "progress_timeline": timeline,
        "strong_subjects": strong_subjects,
        "weak_subjects": weak_subjects,
        "weak_topics": top_weak_topics,
        "study_goals": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "missed_tasks": missed_tasks,
            "planned_hours": planned_hours,
            "completed_hours": completed_hours,
        },
        "suggestions": suggestions,
    }