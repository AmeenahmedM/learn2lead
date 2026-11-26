// auth.js — Handles Health Check, Tab Switching, Login, and Student Registration

const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");

// Switch between Login and Register tabs
tabLogin.addEventListener("click", () => {
  loginForm.classList.remove("hidden");
  registerForm.classList.add("hidden");
  tabLogin.className = "flex-1 py-2.5 text-sm font-bold border-b-2 border-sky-600 text-sky-700";
  tabRegister.className = "flex-1 py-2.5 text-sm font-semibold text-slate-500 hover:text-slate-700";
});

tabRegister.addEventListener("click", () => {
  registerForm.classList.remove("hidden");
  loginForm.classList.add("hidden");
  tabRegister.className = "flex-1 py-2.5 text-sm font-bold border-b-2 border-sky-600 text-sky-700";
  tabLogin.className = "flex-1 py-2.5 text-sm font-semibold text-slate-500 hover:text-slate-700";
});

// 1. Check FastAPI + Neon PostgreSQL Health
async function checkHealth() {
  const badge = document.getElementById("health-badge");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (res.ok) {
      badge.textContent = "Online: " + data.database;
      badge.className = "text-xs font-semibold px-3 py-1 rounded-full bg-emerald-100 text-emerald-800";
    }
  } catch (err) {
    badge.textContent = "Server Offline";
    badge.className = "text-xs font-semibold px-3 py-1 rounded-full bg-rose-100 text-rose-800";
  }
}

// 2. Login Handler (Redirects Student -> /dashboard, Admin -> /admin)
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("login-msg");
  msg.textContent = "Signing in...";
  msg.className = "text-xs font-semibold text-center text-slate-500";

  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: document.getElementById("login-email").value,
      password: document.getElementById("login-password").value,
    }),
  });
  const data = await res.json();
  if (res.ok) {
    localStorage.setItem("l2l_token", data.access_token);
    localStorage.setItem("l2l_user", JSON.stringify(data.user));
    window.location.href = data.user.role === "admin" ? "/admin" : "/dashboard";
  } else {
    msg.textContent = data.detail || "Login failed.";
    msg.className = "text-xs font-semibold text-center text-rose-600";
  }
});

// 3. Register Handler
registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("reg-msg");
  msg.textContent = "Creating account...";
  msg.className = "text-xs font-semibold text-center text-slate-500";

  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: document.getElementById("reg-name").value,
      email: document.getElementById("reg-email").value,
      password: document.getElementById("reg-password").value,
      selected_domain: document.getElementById("reg-domain").value,
    }),
  });
  const data = await res.json();
  if (res.ok) {
    localStorage.setItem("l2l_token", data.access_token);
    localStorage.setItem("l2l_user", JSON.stringify(data.user));
    window.location.href = "/dashboard";
  } else {
    msg.textContent = data.detail || "Registration failed.";
    msg.className = "text-xs font-semibold text-center text-rose-600";
  }
});

checkHealth();
