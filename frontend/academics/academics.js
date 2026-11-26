// academics.js — Frontend JS for Module 1 (Study Planner, AI & Notes Quizzes, Analytics)

const TOKEN = localStorage.getItem("l2l_token");
if (!TOKEN) window.location.href = "/";

function authHeaders(isJson = true) {
  const headers = { "Authorization": "Bearer " + TOKEN };
  if (isJson) headers["Content-Type"] = "application/json";
  return headers;
}

function logout() {
  localStorage.removeItem("l2l_token");
  localStorage.removeItem("l2l_user");
  window.location.href = "/";
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ============================================================================
// 1. STUDY PLANNER PAGE
// ============================================================================
async function initPlannerPage() {
  const dateInput = document.getElementById("task-date");
  if (dateInput) dateInput.value = new Date().toISOString().split("T")[0];

  document.getElementById("subject-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    await fetch("/api/academics/subjects", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        name: document.getElementById("subj-name").value,
        difficulty: document.getElementById("subj-diff").value,
        target_hours_per_week: parseFloat(document.getElementById("subj-hours").value || "5"),
        exam_deadline: document.getElementById("subj-deadline").value || null,
      }),
    });
    e.target.reset();
    loadSubjects();
  });

  document.getElementById("task-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const subjVal = document.getElementById("task-subject").value;
    await fetch("/api/academics/tasks", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        subject_id: subjVal ? parseInt(subjVal, 10) : null,
        title: document.getElementById("task-title").value,
        scheduled_date: document.getElementById("task-date").value,
        duration_mins: parseInt(document.getElementById("task-mins").value || "45", 10),
        priority: document.getElementById("task-priority").value,
      }),
    });
    document.getElementById("task-title").value = "";
    loadTasks();
  });

  document.getElementById("task-filter").addEventListener("change", loadTasks);
  await loadSubjects();
  await loadTasks();
}

async function loadSubjects() {
  const res = await fetch("/api/academics/subjects", { headers: authHeaders() });
  if (res.status === 401) return logout();
  const subjects = await res.json();
  const list = document.getElementById("subjects-list");
  const select = document.getElementById("task-subject");

  select.innerHTML = `<option value="">General Study</option>` +
    subjects.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");

  if (!subjects.length) {
    list.innerHTML = `<p class="text-xs text-slate-400 text-center py-4 bg-slate-50 rounded-xl border border-dashed border-slate-200">No subjects added yet. Add your first subject above!</p>`;
    return;
  }

  list.innerHTML = subjects.map((s, idx) => {
    const diffBadge = s.difficulty === "Hard"
      ? "bg-rose-100 text-rose-700"
      : s.difficulty === "Easy"
        ? "bg-emerald-100 text-emerald-700"
        : "bg-amber-100 text-amber-800";
    return `
      <div style="animation-delay:${Math.min(idx * 50, 300)}ms" class="animate-fade-up flex items-center justify-between p-3.5 rounded-2xl bg-slate-50/90 hover:bg-white border border-slate-200/80 hover:border-sky-200 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200">
        <div>
          <div class="flex items-center gap-2">
            <p class="text-sm font-extrabold text-slate-800">${escapeHtml(s.name)}</p>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${diffBadge}">${escapeHtml(s.difficulty)}</span>
          </div>
          <p class="text-xs text-slate-500 mt-0.5">${s.target_hours_per_week} hrs/wk ${s.exam_deadline ? "&bull; Exam " + escapeHtml(s.exam_deadline) : ""}</p>
        </div>
        <button onclick="deleteSubject(${s.id})" class="px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-xs text-rose-600 font-bold transition cursor-pointer">Delete</button>
      </div>
    `;
  }).join("");
}

async function deleteSubject(id) {
  await fetch(`/api/academics/subjects/${id}`, { method: "DELETE", headers: authHeaders() });
  loadSubjects();
  loadTasks();
}

async function loadTasks() {
  const filter = document.getElementById("task-filter").value;
  const res = await fetch(`/api/academics/tasks?status=${filter}`, { headers: authHeaders() });
  if (res.status === 401) return logout();
  const tasks = await res.json();

  const allRes = await fetch("/api/academics/tasks?status=all", { headers: authHeaders() });
  const allTasks = await allRes.json();
  const done = allTasks.filter(t => t.status === "completed").length;
  const pct = allTasks.length ? Math.round((done / allTasks.length) * 100) : 0;
  document.getElementById("stat-tasks").textContent = `${done} / ${allTasks.length}`;
  document.getElementById("stat-progress").textContent = `${pct}%`;
  const progBar = document.getElementById("planner-progress-bar");
  if (progBar) progBar.style.width = `${pct}%`;

  const container = document.getElementById("tasks-list");
  if (!tasks.length) {
    container.innerHTML = `<p class="text-sm text-slate-400 py-8 text-center bg-slate-50/70 rounded-2xl border border-dashed border-slate-200">No study tasks found. Schedule your first study block above!</p>`;
    return;
  }

  container.innerHTML = tasks.map((t, idx) => {
    const isDone = t.status === "completed";
    const badgeColor = t.priority === "High" ? "bg-rose-100 text-rose-700"
                     : t.priority === "Low" ? "bg-slate-100 text-slate-600"
                     : "bg-amber-100 text-amber-800";
    return `
      <div style="animation-delay:${Math.min(idx * 45, 320)}ms" class="animate-fade-up flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-2xl border transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${isDone ? "bg-emerald-50/70 border-emerald-200" : "bg-white border-slate-200/90 hover:border-sky-200"}">
        <div class="flex items-center gap-3">
          <input type="checkbox" ${isDone ? "checked" : ""} onchange="toggleTask(${t.id}, this.checked)"
                 class="h-4 w-4 accent-emerald-600 rounded cursor-pointer transition-transform active:scale-90" />
          <div>
            <p class="text-sm font-bold transition-colors ${isDone ? "line-through text-slate-400" : "text-slate-900"}">${escapeHtml(t.title)}</p>
            <p class="text-xs text-slate-500">${escapeHtml(t.subject_name)} &bull; ${escapeHtml(t.scheduled_date)} &bull; ${t.duration_mins} mins</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full ${badgeColor}">${escapeHtml(t.priority)}</span>
          <button onclick="deleteTask(${t.id})" class="px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-xs text-rose-600 font-bold transition cursor-pointer">Delete</button>
        </div>
      </div>
    `;
  }).join("");
}

async function toggleTask(id, checked) {
  await fetch(`/api/academics/tasks/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ status: checked ? "completed" : "pending" }),
  });
  loadTasks();
}

async function deleteTask(id) {
  await fetch(`/api/academics/tasks/${id}`, { method: "DELETE", headers: authHeaders() });
  loadTasks();
}

// ============================================================================
// 2. AI & NOTES-BASED SUBJECT QUIZZES PAGE (15 MCQs)
// ============================================================================
let activeQuizId = null;

function setQuizMode(mode) {
  document.getElementById("gen-mode").value = mode;
  const aiBtn = document.getElementById("mode-ai-btn");
  const notesBtn = document.getElementById("mode-notes-btn");
  const notesBox = document.getElementById("notes-upload-box");

  if (mode === "upload_notes") {
    notesBox.classList.remove("hidden");
    notesBtn.className = "group relative py-4 px-5 rounded-2xl border-2 border-emerald-500 bg-gradient-to-br from-emerald-50 to-teal-50/60 text-emerald-950 text-sm font-bold text-left shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md cursor-pointer";
    aiBtn.className = "group relative py-4 px-5 rounded-2xl border-2 border-slate-200 bg-white text-slate-700 text-sm font-bold text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md cursor-pointer";
  } else {
    notesBox.classList.add("hidden");
    aiBtn.className = "group relative py-4 px-5 rounded-2xl border-2 border-sky-500 bg-gradient-to-br from-sky-50 to-indigo-50/60 text-sky-950 text-sm font-bold text-left shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md cursor-pointer";
    notesBtn.className = "group relative py-4 px-5 rounded-2xl border-2 border-slate-200 bg-white text-slate-700 text-sm font-bold text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md cursor-pointer";
  }
}

async function initQuizzesPage() {
  await populateSchedulePicker();

  const picker = document.getElementById("schedule-picker");
  picker.addEventListener("change", (e) => {
    if (!e.target.value) return;
    const [subj, topic] = e.target.value.split("|||");
    document.getElementById("gen-subject").value = subj;
    document.getElementById("gen-topic").value = topic;
  });

  document.getElementById("generate-quiz-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("gen-submit-btn");
    const status = document.getElementById("gen-status");
    const mode = document.getElementById("gen-mode").value;
    const countVal = document.getElementById("gen-count").value || "15";

    const formData = new FormData();
    formData.append("subject_name", document.getElementById("gen-subject").value.trim());
    formData.append("topic_name", document.getElementById("gen-topic").value.trim());
    formData.append("mode", mode);
    formData.append("num_questions", countVal);

    if (mode === "upload_notes") {
      formData.append("pasted_notes", document.getElementById("gen-pasted-notes").value || "");
      const fileInput = document.getElementById("gen-notes-file");
      if (fileInput.files.length > 0) {
        formData.append("notes_file", fileInput.files[0]);
      }
    }

    btn.disabled = true;
    btn.innerHTML = `<svg class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg> Generating with Gemini AI...`;
    status.textContent = `Creating ${countVal} technical MCQs and saving to PostgreSQL (takes ~5-10 seconds)...`;
    status.className = "text-xs font-semibold text-sky-700 animate-pulse";

    try {
      const res = await fetch("/api/academics/quizzes/generate", {
        method: "POST",
        headers: authHeaders(false),
        body: formData,
      });

      if (res.status === 401) {
        status.textContent = "Your login session expired. Please click Logout and sign in again.";
        status.className = "text-xs font-bold text-rose-600";
        return;
      }

      const rawText = await res.text();
      let data = {};
      try {
        data = JSON.parse(rawText);
      } catch {
        data = { detail: rawText || `Server error (${res.status})` };
      }

      if (res.ok) {
        status.textContent = `${data.message || "Quiz generated!"} Opening your questions below...`;
        status.className = "text-xs font-bold text-emerald-700";
        await loadQuizzes();
        if (data.quiz_id) {
          await startQuiz(data.quiz_id);
        }
      } else {
        status.textContent = data.detail || "Failed to generate quiz.";
        status.className = "text-xs font-bold text-rose-600";
      }
    } catch (err) {
      status.textContent = "Network error: Could not reach FastAPI backend. Make sure uvicorn is running.";
      status.className = "text-xs font-bold text-rose-600";
    } finally {
      btn.disabled = false;
      btn.textContent = "Generate 15-Question Quiz";
    }
  });

  await loadQuizzes();
  await loadQuizHistory();
}

async function populateSchedulePicker() {
  try {
    const [tasksRes, subjRes] = await Promise.all([
      fetch("/api/academics/tasks?status=all", { headers: authHeaders() }),
      fetch("/api/academics/subjects", { headers: authHeaders() }),
    ]);
    if (tasksRes.status === 401 || subjRes.status === 401) return logout();

    const tasks = await tasksRes.json();
    const subjects = await subjRes.json();
    const picker = document.getElementById("schedule-picker");

    const options = [];
    const seen = new Set();

    tasks.forEach(t => {
      const key = `${t.subject_name}|||${t.title}`;
      if (!seen.has(key.toLowerCase())) {
        seen.add(key.toLowerCase());
        options.push(`<option value="${escapeHtml(key)}">${escapeHtml(t.subject_name)} — ${escapeHtml(t.title)} (Scheduled ${escapeHtml(t.scheduled_date)})</option>`);
      }
    });

    subjects.forEach(s => {
      const key = `${s.name}|||${s.name} Core Concepts`;
      if (!seen.has(key.toLowerCase())) {
        seen.add(key.toLowerCase());
        options.push(`<option value="${escapeHtml(key)}">${escapeHtml(s.name)} — Core Concepts</option>`);
      }
    });

    picker.innerHTML = `<option value="">-- Select from your Study Planner or type below --</option>` + options.join("");
  } catch (err) {
    console.error("Failed to load schedule picker:", err);
  }
}

let recentAttemptsCount = 0;
let activeViewedAttemptId = null;

function updateViewButtonsUI() {
  document.querySelectorAll("button[data-view-attempt-id]").forEach(btn => {
    const isViewing = Number(btn.dataset.viewAttemptId) === activeViewedAttemptId;
    btn.textContent = isViewing ? "Close" : "View";
    btn.className = isViewing
      ? "px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold rounded-xl transition-all duration-200 active:scale-95 cursor-pointer"
      : "px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-xs font-bold rounded-xl transition-all duration-200 active:scale-95 cursor-pointer";
  });
}

function closeQuizResult() {
  const box = document.getElementById("quiz-result");
  if (box) box.classList.add("hidden");
  activeViewedAttemptId = null;
  updateViewButtonsUI();
}

function updateHistoryButtonLabel() {
  const btn = document.getElementById("toggle-history-btn");
  const sec = document.getElementById("recent-attempts-section");
  if (!btn || !sec) return;
  const isHidden = sec.classList.contains("hidden");
  const countText = recentAttemptsCount > 0 ? ` (${recentAttemptsCount})` : "";
  btn.textContent = isHidden
    ? `View Recent Attempted Quizzes${countText}`
    : `Close Recent Attempted Quizzes${countText}`;
}

function toggleRecentAttempts(forceState) {
  const sec = document.getElementById("recent-attempts-section");
  if (!sec) return;
  const shouldShow = typeof forceState === "boolean" ? forceState : sec.classList.contains("hidden");
  sec.classList.toggle("hidden", !shouldShow);
  updateHistoryButtonLabel();
  if (shouldShow) {
    sec.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

async function loadQuizzes() {
  const res = await fetch("/api/academics/quizzes", { headers: authHeaders() });
  if (res.status === 401) return logout();
  const quizzes = await res.json();
  const grid = document.getElementById("quizzes-grid");
  const section = document.getElementById("pending-quizzes-section");

  // Only show quizzes that have not been finished yet
  const pendingQuizzes = quizzes.filter(q => q.last_score === null);

  if (!pendingQuizzes.length) {
    if (section) section.classList.add("hidden");
    grid.innerHTML = "";
    return;
  }

  if (section) section.classList.remove("hidden");
  grid.innerHTML = pendingQuizzes.map((q, idx) => `
    <div style="animation-delay:${idx * 70}ms" class="animate-fade-up bg-white/95 rounded-2xl border border-slate-200/80 p-5 shadow-md hover:shadow-xl hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between">
      <div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs font-extrabold text-sky-600 uppercase tracking-wide">${escapeHtml(q.subject_or_domain)}</span>
          <span class="text-[10px] font-bold px-2.5 py-0.5 rounded-full ${q.source_type === "From Notes" ? "bg-emerald-100 text-emerald-800" : "bg-indigo-100 text-indigo-800"}">${escapeHtml(q.source_type)}</span>
        </div>
        <h3 class="text-base font-extrabold text-slate-900 mt-1.5">${escapeHtml(q.title)}</h3>
        <p class="text-xs text-slate-500 mt-1">${q.question_count} Questions &bull; ${q.duration_mins} mins</p>
      </div>
      <div class="mt-5 flex gap-2">
        <button onclick="startQuiz(${q.id})" class="btn-shimmer flex-1 py-2.5 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-sm transition-all active:scale-95 cursor-pointer">Start Quiz</button>
        <button onclick="deleteQuiz(${q.id})" class="px-3.5 py-2.5 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-bold rounded-xl transition-all active:scale-95 cursor-pointer">Delete</button>
      </div>
    </div>
  `).join("");
}

async function deleteQuiz(id) {
  await fetch(`/api/academics/quizzes/${id}`, { method: "DELETE", headers: authHeaders() });
  loadQuizzes();
  loadQuizHistory();
}

async function startQuiz(quizId) {
  activeQuizId = quizId;
  const res = await fetch(`/api/academics/quizzes/${quizId}`, { headers: authHeaders() });
  if (res.status === 401) return logout();
  const quiz = await res.json();

  if (!res.ok || !quiz.questions || !quiz.questions.length) {
    const status = document.getElementById("gen-status");
    if (status) {
      status.textContent = quiz.detail || "No questions found for this quiz.";
      status.className = "text-xs font-bold text-rose-600";
    }
    return;
  }

  document.getElementById("quiz-result").classList.add("hidden");
  activeViewedAttemptId = null;
  updateViewButtonsUI();
  const runner = document.getElementById("quiz-runner");
  runner.classList.remove("hidden");
  document.getElementById("runner-title").textContent = quiz.title;
  document.getElementById("runner-meta").textContent = `${quiz.subject_or_domain} • ${quiz.questions.length} MCQs`;

  const form = document.getElementById("quiz-submit-form");
  const totalQ = quiz.questions.length;
  const progressBar = document.getElementById("runner-progress-bar");
  const progressText = document.getElementById("runner-progress-text");
  if (progressBar) progressBar.style.width = "0%";
  if (progressText) progressText.textContent = `0 / ${totalQ} Answered`;

  form.innerHTML = quiz.questions.map((q, idx) => `
    <div style="animation-delay:${Math.min(idx * 40, 400)}ms" class="animate-fade-up p-5 rounded-2xl bg-slate-50/80 border border-slate-200/80 space-y-3 hover:border-sky-200 transition-colors">
      <p class="text-sm font-extrabold text-slate-900 leading-relaxed">
        <span class="inline-flex items-center justify-center h-6 w-6 rounded-lg bg-sky-100 text-sky-800 text-xs font-black mr-2">${idx + 1}</span>
        ${escapeHtml(q.question_text)}
      </p>
      <div class="space-y-2 pl-1">
        ${q.options.map(opt => `
          <label class="mcq-option flex items-center gap-3 p-3 rounded-xl bg-white border border-slate-200 text-sm text-slate-700 cursor-pointer">
            <input type="radio" name="q_${q.id}" value="${escapeHtml(opt)}" required class="h-4 w-4 accent-sky-600 shrink-0" />
            <span class="font-medium">${escapeHtml(opt)}</span>
          </label>
        `).join("")}
      </div>
    </div>
  `).join("") + `
    <div class="pt-2 flex justify-end">
      <button type="submit" class="btn-shimmer px-7 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 active:scale-[0.98] text-white text-sm font-bold rounded-xl shadow-lg shadow-emerald-600/25 transition-all cursor-pointer">
        Submit Quiz &amp; View Score
      </button>
    </div>
  `;

  // Live progress bar update as student selects answers
  form.onchange = () => {
    const answered = quiz.questions.filter(q => form.querySelector(`input[name="q_${q.id}"]:checked`)).length;
    const pct = totalQ ? Math.round((answered / totalQ) * 100) : 0;
    if (progressBar) progressBar.style.width = `${pct}%`;
    if (progressText) progressText.textContent = `${answered} / ${totalQ} Answered`;
  };

  runner.scrollIntoView({ behavior: "smooth", block: "start" });

  form.onsubmit = async (e) => {
    e.preventDefault();
    const answers = {};
    quiz.questions.forEach(q => {
      const checked = form.querySelector(`input[name="q_${q.id}"]:checked`);
      if (checked) answers[String(q.id)] = checked.value;
    });

    const subRes = await fetch(`/api/academics/quizzes/${activeQuizId}/submit`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ answers }),
    });
    const result = await subRes.json();
    showQuizResult(result);
    loadQuizzes();
    loadQuizHistory();
  };
}

function closeQuizRunner() {
  document.getElementById("quiz-runner").classList.add("hidden");
}

async function viewQuizAttempt(attemptId) {
  const resultBox = document.getElementById("quiz-result");
  const status = document.getElementById("gen-status");
  if (activeViewedAttemptId === attemptId && resultBox && !resultBox.classList.contains("hidden")) {
    closeQuizResult();
    return;
  }

  const res = await fetch(`/api/academics/quiz-history/${attemptId}`, { headers: authHeaders() });
  if (res.status === 401) return logout();
  const data = await res.json();
  if (!res.ok) {
    if (status) {
      status.textContent = res.status === 404 && data.detail === "Not Found"
        ? "Backend route missing: please copy the updated academics.py into backend/routers/academics.py and save."
        : (data.detail || "Could not load quiz attempt review.");
      status.className = "text-xs font-bold text-rose-600";
    }
    return;
  }

  if (status) status.textContent = "";
  activeViewedAttemptId = attemptId;
  showQuizResult(data);
  updateViewButtonsUI();
}

function showQuizResult(result) {
  document.getElementById("quiz-runner").classList.add("hidden");
  const box = document.getElementById("quiz-result");
  box.classList.remove("hidden");
  const subtitle = result.quiz_title
    ? `<p class="text-xs font-bold uppercase tracking-wider text-sky-700 mb-1">${escapeHtml(result.quiz_title)}${result.completed_at ? " • Attempted " + escapeHtml(result.completed_at) : ""}</p>`
    : "";

  const scoreNum = Number(result.score_percent || 0);
  const ringColor = scoreNum >= 75 ? "#10b981" : scoreNum < 60 ? "#f43f5e" : "#f59e0b";
  const radius = 32;
  const circumference = 2 * Math.PI * radius;
  const targetOffset = circumference - (Math.min(100, Math.max(0, scoreNum)) / 100) * circumference;

  box.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
      <div class="flex items-center gap-4">
        <div class="relative h-20 w-20 shrink-0">
          <svg class="h-20 w-20 -rotate-90" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="${radius}" fill="none" stroke="#e2e8f0" stroke-width="7"></circle>
            <circle id="score-ring-arc" class="score-ring-progress" cx="40" cy="40" r="${radius}" fill="none" stroke="${ringColor}" stroke-width="7" stroke-linecap="round"
                    stroke-dasharray="${circumference}" stroke-dashoffset="${circumference}"></circle>
          </svg>
          <span class="absolute inset-0 flex items-center justify-center text-sm font-black text-slate-900">${scoreNum}%</span>
        </div>
        <div>
          ${subtitle}
          <h2 class="text-2xl font-black text-slate-900">Score: ${result.score_percent}% <span class="text-base font-bold text-slate-500">(${result.correct_count}/${result.total_questions})</span></h2>
          <p class="text-xs text-slate-600 mt-1">${result.weak_topics.length ? "Weak topics to revise: <strong class='text-rose-700'>" + escapeHtml(result.weak_topics.join(", ")) + "</strong>" : "<strong class='text-emerald-700'>Outstanding! No weak topics detected.</strong>"}</p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        ${result.quiz_id ? `<button type="button" onclick="startQuiz(${result.quiz_id})" class="px-4 py-2 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-sm transition-all active:scale-95 cursor-pointer">Retake Quiz</button>` : ""}
        <a href="/static/academics/analytics.html" class="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl transition-all">View Analytics</a>
        <button type="button" onclick="closeQuizResult()" class="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all cursor-pointer">Close</button>
      </div>
    </div>
    <div class="space-y-3">
      ${result.review.map((r, i) => `
        <div style="animation-delay:${Math.min(i * 45, 450)}ms" class="animate-fade-up p-4 rounded-2xl border ${r.is_correct ? "bg-emerald-50/70 border-emerald-200" : "bg-rose-50/70 border-rose-200"} text-sm transition-all hover:shadow-sm">
          <div class="flex items-start justify-between gap-2">
            <p class="font-bold text-slate-900">${i + 1}. ${escapeHtml(r.question_text)}</p>
            <span class="shrink-0 text-[11px] font-extrabold px-2.5 py-0.5 rounded-full ${r.is_correct ? "bg-emerald-200/80 text-emerald-900" : "bg-rose-200/80 text-rose-900"}">
              ${r.is_correct ? "✓ Correct" : "✕ Wrong"}
            </span>
          </div>
          <p class="text-xs mt-2">Your answer: <strong class="${r.is_correct ? "text-emerald-800" : "text-rose-700"}">${escapeHtml(r.selected)}</strong> &bull; Correct answer: <strong class="text-emerald-800">${escapeHtml(r.correct_answer)}</strong></p>
          ${r.explanation ? `<p class="text-xs text-slate-600 mt-1.5 leading-relaxed">${escapeHtml(r.explanation)}</p>` : ""}
        </div>
      `).join("")}
    </div>
  `;

  // Trigger smooth SVG ring fill animation on next frame
  requestAnimationFrame(() => {
    const arc = document.getElementById("score-ring-arc");
    if (arc) arc.style.strokeDashoffset = String(targetOffset);
  });

  box.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadQuizHistory() {
  const res = await fetch("/api/academics/quiz-history", { headers: authHeaders() });
  if (res.status === 401) return logout();
  const rows = await res.json();
  recentAttemptsCount = rows.length;
  updateHistoryButtonLabel();

  const tbody = document.getElementById("history-tbody");

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="py-4 text-center text-slate-400">No quiz attempts yet. Generate and finish a quiz above!</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(r => `
    <tr class="hover:bg-sky-50/50 transition-colors duration-150">
      <td class="py-3 pr-4 text-xs text-slate-500">${escapeHtml(r.completed_at)}</td>
      <td class="py-3 pr-4 font-bold text-slate-800">${escapeHtml(r.subject)}</td>
      <td class="py-3 pr-4 font-medium text-slate-700">${escapeHtml(r.quiz_title)}</td>
      <td class="py-3 pr-4">
        <span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-extrabold ${r.score_percent >= 75 ? "bg-emerald-100 text-emerald-700" : r.score_percent < 60 ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"}">${r.score_percent}%</span>
      </td>
      <td class="py-3 pr-4 text-xs text-slate-600">${r.weak_topics.length ? escapeHtml(r.weak_topics.join(", ")) : "<span class='text-emerald-600 font-semibold'>None</span>"}</td>
      <td class="py-3">
        <div class="flex items-center gap-2">
          <button type="button" data-view-attempt-id="${r.attempt_id}" onclick="viewQuizAttempt(${r.attempt_id})" class="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-xs font-bold rounded-xl transition-all duration-200 active:scale-95 cursor-pointer">View</button>
          <button type="button" onclick="startQuiz(${r.quiz_id})" class="px-3 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200 text-xs font-bold rounded-xl transition-all duration-200 active:scale-95 cursor-pointer">Retake</button>
        </div>
      </td>
    </tr>
  `).join("");
  updateViewButtonsUI();
}

// ============================================================================
// 3. ACADEMIC ANALYTICS PAGE (Chart.js)
// ============================================================================
async function initAnalyticsPage() {
  const res = await fetch("/api/academics/analytics", { headers: authHeaders() });
  if (res.status === 401) return logout();
  const data = await res.json();

  document.getElementById("kpi-avg").textContent = `${data.overall_avg_score}%`;
  document.getElementById("kpi-attempts").textContent = data.total_attempts;
  document.getElementById("kpi-hours").textContent = `${data.study_goals.completed_hours} / ${data.study_goals.planned_hours} hrs`;
  if (data.score_delta !== null) {
    const sign = data.score_delta >= 0 ? "+" : "";
    document.getElementById("kpi-delta").textContent = `${sign}${data.score_delta}%`;
    document.getElementById("kpi-delta").className = `text-3xl font-black mt-2 ${data.score_delta >= 0 ? "text-emerald-600" : "text-rose-600"}`;
  }

  document.getElementById("strong-list").textContent = data.strong_subjects.length ? data.strong_subjects.join(", ") : "Take quizzes to unlock";
  document.getElementById("weak-list").textContent = data.weak_subjects.length ? data.weak_subjects.join(", ") : "None below 65%";
  document.getElementById("suggestions-list").innerHTML = data.suggestions.map((s, idx) => `
    <li style="animation-delay:${idx * 60}ms" class="animate-fade-up flex items-start gap-2.5 p-3 rounded-2xl bg-slate-50/90 border border-slate-200/70">
      <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sky-700 text-xs font-black">${idx + 1}</span>
      <span class="font-medium text-slate-700">${escapeHtml(s)}</span>
    </li>
  `).join("");

  new Chart(document.getElementById("subjectChart"), {
    type: "bar",
    data: {
      labels: data.subject_averages.map(s => s.subject),
      datasets: [{
        label: "Average Score (%)",
        data: data.subject_averages.map(s => s.avg_score),
        backgroundColor: "rgba(2, 132, 199, 0.85)",
        hoverBackgroundColor: "#4f46e5",
        borderRadius: 10,
        borderSkipped: false,
      }],
    },
    options: {
      animation: { duration: 900, easing: "easeOutQuart" },
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: "rgba(148, 163, 184, 0.15)" } },
        x: { grid: { display: false } },
      },
    },
  });

  new Chart(document.getElementById("timelineChart"), {
    type: "line",
    data: {
      labels: data.progress_timeline.map(p => p.label),
      datasets: [{
        label: "Quiz Score (%)",
        data: data.progress_timeline.map(p => p.score),
        borderColor: "#10b981",
        backgroundColor: "rgba(16, 185, 129, 0.14)",
        pointBackgroundColor: "#059669",
        pointBorderColor: "#ffffff",
        pointBorderWidth: 2,
        pointRadius: 5,
        pointHoverRadius: 7,
        fill: true,
        tension: 0.35,
      }],
    },
    options: {
      animation: { duration: 1000, easing: "easeOutQuart" },
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: "rgba(148, 163, 184, 0.15)" } },
        x: { grid: { display: false } },
      },
    },
  });

  new Chart(document.getElementById("goalChart"), {
    type: "doughnut",
    data: {
      labels: ["Completed", "Pending", "Missed"],
      datasets: [{
        data: [
          data.study_goals.completed_tasks,
          data.study_goals.pending_tasks,
          data.study_goals.missed_tasks,
        ],
        backgroundColor: ["#10b981", "#f59e0b", "#f43f5e"],
        borderWidth: 3,
        borderColor: "#ffffff",
        hoverOffset: 8,
      }],
    },
    options: {
      cutout: "66%",
      animation: { animateRotate: true, animateScale: true, duration: 950 },
      plugins: {
        legend: { position: "bottom", labels: { usePointStyle: true, padding: 16 } },
      },
    },
  });
}