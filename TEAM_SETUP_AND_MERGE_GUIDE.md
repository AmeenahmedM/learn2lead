# Learn2Lead — 3-Member Team Setup, Build & Merge Guide

## 1. First-Time Setup in VS Code (All 3 Members Do This Once)

1. Unzip `learn2lead_base.zip` and open the `learn2lead` folder in **VS Code**.
2. Open the `.env` file and paste the team's Neon PostgreSQL link after `DATABASE_URL=` (save the file with `Ctrl + S`).
3. Open a terminal in VS Code (`Terminal → New Terminal`) and run:
   ```bash
   python -m venv venv
   source venv/Scripts/activate      # Git Bash (or: venv\Scripts\activate in PowerShell)
   pip install -r requirements.txt
   uvicorn backend.main:app --reload
   ```
4. Open **http://127.0.0.1:8000** in your browser.
   - Verify the top-right badge says **Online: PostgreSQL Connected**.
   - Test Login with **Student** (`student@learn2lead.com` / `Student@123`) or **Admin** (`admin@learn2lead.com` / `Admin@123`).

---

## 2. Assigned Modules & Files (Zero Overlap!)

> **Golden Rule:** NEVER edit `backend/models.py`, `backend/database.py`, or `backend/auth_utils.py`.

| Member | Module Name | Exact Files They Create & Own |
| :--- | :--- | :--- |
| **Member 1 (Team Lead)** | **Module 1: Academics** | `backend/routers/academics.py` + `frontend/academics/` |
| **Member 2** | **Module 2: Employability & Roadmaps** | `backend/routers/employability.py` + `frontend/employability/` |
| **Member 3** | **Module 3: AI Recommender, Trends & Admin** | `backend/routers/admin_insights.py` + `frontend/admin_insights/` |

---

## 3. Pushing Your Module to Your Own GitHub Account

Once your assigned module works locally, push it to your own GitHub repo:
```bash
git init
git add .
git commit -m "Completed my Learn2Lead module"
git branch -M main
git remote add origin https://github.com/<YOUR-USERNAME>/<YOUR-REPO>.git
git push -u origin main
```
*(`.env` is in `.gitignore`, so your database password stays private!)*

---

## 4. Sharing ZIPs & Merging So All 3 Laptops Have the Complete App

1. **Zip ONLY your 2 owned items** and send them in your team group:
   - Member 1 zips `backend/routers/academics.py` + `frontend/academics/` → `module1_academics.zip`
   - Member 2 zips `backend/routers/employability.py` + `frontend/employability/` → `module2_employability.zip`
   - Member 3 zips `backend/routers/admin_insights.py` + `frontend/admin_insights/` → `module3_admin_insights.zip`
2. **Extract the other 2 ZIPs** into your `learn2lead/` folder (matching `backend/routers/` and `frontend/`). Nothing will be overwritten!
3. Open `backend/main.py` and **uncomment** the 2 lines under each module's plug-in slot:
   ```python
   from .routers import academics
   app.include_router(academics.router)

   from .routers import employability
   app.include_router(employability.router)

   from .routers import admin_insights
   app.include_router(admin_insights.router)
   ```
4. Restart the server (`uvicorn backend.main:app --reload`) — **all 3 members now have the full, working Learn2Lead web app!**
