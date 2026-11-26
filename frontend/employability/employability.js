const TOKEN = localStorage.getItem("l2l_token");
if (!TOKEN) window.location.href = "/";

function logout() {
  localStorage.removeItem("l2l_token");
  localStorage.removeItem("l2l_user");
  window.location.href = "/";
}

const headers = { "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json" };

async function loadDomains() {
  const response = await fetch("/api/employability/domains", { headers });
  if (response.status === 401) return logout();
  const domains = await response.json();
  document.getElementById("domain-select").innerHTML = domains
    .map(d => `<option value="${d.id}">${d.name}</option>`)
    .join("");
}

async function loadRoadmap() {
  const response = await fetch("/api/employability/roadmap", { headers });
  if (!response.ok) return;
  const data = await response.json();
  if (!data.domain) return;

  document.getElementById("domain-name").textContent = data.domain.name;
  document.getElementById("domain-description").textContent = data.domain.description;
  document.getElementById("domain-select").value = data.domain.id;

  const completed = data.steps.filter(s => s.status === "completed").length;
  const percent = data.steps.length ? Math.round(completed / data.steps.length * 100) : 0;
  document.getElementById("domain-progress").textContent = percent + "%";

  document.getElementById("roadmap-list").innerHTML = data.steps.length
    ? data.steps.map((step, index) => `
      <div class="flex items-start gap-3 rounded-2xl border border-slate-200 p-4">
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-black text-indigo-700">${index + 1}</span>
        <div class="min-w-0 flex-1">
          <p class="font-bold text-slate-900">${step.skill_name}</p>
          <p class="mt-1 text-xs text-slate-500">${step.description || ""}</p>
        </div>
        <select onchange="updateRoadmap(${step.id}, this.value)" class="rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-bold">
          <option value="not_started" ${step.status === "not_started" ? "selected" : ""}>Not started</option>
          <option value="in_progress" ${step.status === "in_progress" ? "selected" : ""}>In progress</option>
          <option value="completed" ${step.status === "completed" ? "selected" : ""}>Completed</option>
        </select>
      </div>`).join("")
    : `<p class="rounded-2xl border border-dashed p-6 text-center text-sm text-slate-400">No roadmap steps available.</p>`;
}

async function updateRoadmap(stepId, status) {
  await fetch(`/api/employability/roadmap/${stepId}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify({ status }),
  });
  await Promise.all([loadRoadmap(), loadReadiness()]);
}

async function loadReadiness() {
  const response = await fetch("/api/employability/readiness", { headers });
  if (!response.ok) return;
  const data = await response.json();
  const score = Math.round(data.overall_score);
  document.getElementById("readiness-score").textContent = score;
  document.getElementById("readiness-bar").style.width = score + "%";

  document.getElementById("readiness-breakdown").innerHTML = Object.entries(data.category_scores)
    .map(([key, value]) => `
      <div>
        <div class="flex justify-between text-xs font-bold">
          <span class="capitalize text-slate-500">${key.replace("_", " ")}</span>
          <span>${Math.round(value)}%</span>
        </div>
        <div class="mt-1 h-2 rounded-full bg-slate-100">
          <div class="h-full rounded-full bg-indigo-500" style="width:${Math.max(0, Math.min(100, value))}%"></div>
        </div>
      </div>`).join("");
}

document.getElementById("select-domain").addEventListener("click", async () => {
  await fetch("/api/employability/domains/select", {
    method: "POST",
    headers,
    body: JSON.stringify({ domain_id: Number(document.getElementById("domain-select").value) }),
  });
  await Promise.all([loadRoadmap(), loadReadiness()]);
});

document.getElementById("record-readiness").addEventListener("click", async () => {
  const response = await fetch("/api/employability/readiness/record", { method: "POST", headers });
  if (response.ok) alert("Readiness snapshot recorded.");
});

Promise.all([loadDomains(), loadRoadmap(), loadReadiness()]);
