const TOKEN = localStorage.getItem("l2l_token");
if (!TOKEN) window.location.href = "/";

function logout() {
  localStorage.removeItem("l2l_token");
  localStorage.removeItem("l2l_user");
  window.location.href = "/";
}

const headers = { "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json" };

async function loadHistory() {
  const response = await fetch("/api/leadership/readiness-history", { headers });
  if (response.status === 401) return logout();
  const history = await response.json();
  document.getElementById("snapshot-count").textContent = history.length;

  if (history.length) {
    const latest = history[history.length - 1].overall_score;
    document.getElementById("latest-score").textContent = Math.round(latest);
    if (history.length > 1) {
      const growth = latest - history[0].overall_score;
      document.getElementById("score-growth").textContent = (growth >= 0 ? "+" : "") + growth.toFixed(1);
    } else {
      document.getElementById("score-growth").textContent = "0";
    }
  } else {
    document.getElementById("latest-score").textContent = "--";
    document.getElementById("score-growth").textContent = "--";
  }

  document.getElementById("history-list").innerHTML = history.length
    ? history.slice().reverse().map(item => `
      <div class="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-2">
        <span class="text-xs text-slate-500">${new Date(item.recorded_at).toLocaleString()}</span>
        <span class="font-black text-slate-900">${Math.round(item.overall_score)}%</span>
      </div>`).join("")
    : `<p class="rounded-2xl border border-dashed p-5 text-center text-sm text-slate-400">Record a readiness snapshot from Module 2.</p>`;
}

async function loadRecommendations() {
  const response = await fetch("/api/leadership/recommendations", { headers });
  if (!response.ok) return;
  const rows = await response.json();
  document.getElementById("recommendation-list").innerHTML = rows.length
    ? rows.map(row => `
      <div class="rounded-2xl border border-slate-200 p-4">
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="font-bold text-slate-900">${row.recommended_topic}</p>
            <p class="mt-1 text-xs text-slate-500">${row.reason}</p>
          </div>
          <span class="shrink-0 rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold uppercase">${row.status}</span>
        </div>
        <div class="mt-3 flex gap-2">
          <button onclick="updateRecommendation(${row.id}, 'followed')" class="rounded-lg border px-2.5 py-1 text-xs font-bold">Following</button>
          <button onclick="updateRecommendation(${row.id}, 'improved')" class="rounded-lg border px-2.5 py-1 text-xs font-bold text-emerald-700">Improved</button>
        </div>
      </div>`).join("")
    : `<p class="rounded-2xl border border-dashed p-5 text-center text-sm text-slate-400">Generate a recommendation to begin.</p>`;
}

async function updateRecommendation(id, status) {
  await fetch(`/api/leadership/recommendations/${id}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify({ status }),
  });
  loadRecommendations();
}

document.getElementById("generate-recommendation").addEventListener("click", async () => {
  await fetch("/api/leadership/recommendations/generate", { method: "POST", headers });
  loadRecommendations();
});

async function loadMarketTrends() {
  const response = await fetch("/api/leadership/market-trends", { headers });
  if (!response.ok) return;
  const trends = await response.json();
  document.getElementById("market-trends").innerHTML = trends.length
    ? trends.map(trend => `
      <div class="rounded-2xl border border-slate-200 p-4">
        <div class="flex items-center justify-between">
          <p class="text-sm font-bold">${trend.role_title}</p>
          <span class="text-xl font-black text-emerald-700">${trend.demand_index}</span>
        </div>
        <p class="mt-2 text-xs text-slate-500">${trend.in_demand_skills.join(" · ")}</p>
      </div>`).join("")
    : `<p class="text-sm text-slate-400">No market trend data available.</p>`;
}

const scenarios = [
  {
    text: "A teammate misses an important deadline because they misunderstood priorities. The client is asking for an update. What is the strongest leadership response?",
    options: [
      { text: "Publicly criticize the teammate", score: 0 },
      { text: "Clarify impact, listen privately, reset priorities, and agree on a recovery plan", score: 1 },
      { text: "Ignore the deadline and continue working", score: 0 },
    ],
  },
  {
    text: "Your team disagrees on the best technical approach. What should you do first?",
    options: [
      { text: "Choose the strongest person's opinion", score: 0 },
      { text: "Define decision criteria and invite evidence from everyone", score: 1 },
      { text: "Avoid the decision", score: 0 },
    ],
  },
];
let scenarioIndex = 0;

function renderScenario() {
  const scenario = scenarios[scenarioIndex];
  document.getElementById("scenario-text").textContent = scenario.text;
  document.getElementById("scenario-feedback").className = "mt-3 hidden rounded-xl border p-3 text-sm";
  document.getElementById("scenario-options").innerHTML = scenario.options.map((option, index) =>
    `<button onclick="answerScenario(${index})" class="rounded-xl border border-slate-200 px-3 py-3 text-left text-sm font-semibold hover:border-emerald-300 hover:bg-emerald-50">${option.text}</button>`
  ).join("");
}

function answerScenario(index) {
  const scenario = scenarios[scenarioIndex];
  const correct = scenario.options[index].score === 1;
  const feedback = document.getElementById("scenario-feedback");
  feedback.className = `mt-3 rounded-xl border p-3 text-sm ${correct ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800"}`;
  feedback.textContent = correct ? "Strong choice: this approach is collaborative and accountable." : "Consider listening, clarifying impact, and aligning the team around a clear plan.";
  setTimeout(() => {
    scenarioIndex = (scenarioIndex + 1) % scenarios.length;
    renderScenario();
  }, 2200);
}

renderScenario();
Promise.all([loadHistory(), loadRecommendations(), loadMarketTrends()]);
