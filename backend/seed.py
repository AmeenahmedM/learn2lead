"""
seed.py — Inserts starter Admin/Student accounts, Career Domains, Readiness Weights,
and baseline Job Market Trends into PostgreSQL on first startup.
"""
from sqlalchemy.orm import Session
from .models import User, ReadinessConfig, CareerDomain, RoadmapStep, MarketTrend
from .auth_utils import hash_password


def seed_initial_data(db: Session):
    # 1. Seed default Admin and Demo Student accounts
    if not db.query(User).filter(User.email == "admin@learn2lead.com").first():
        db.add(User(
            name="Learn2Lead Admin",
            email="admin@learn2lead.com",
            password_hash=hash_password("Admin@123"),
            role="admin",
            selected_domain="DevOps & Cloud Engineering",
        ))

    if not db.query(User).filter(User.email == "student@learn2lead.com").first():
        db.add(User(
            name="Demo Student",
            email="student@learn2lead.com",
            password_hash=hash_password("Student@123"),
            role="student",
            selected_domain="DevOps & Cloud Engineering",
        ))

    # 2. Seed default Placement Readiness Score weights (totals 100%)
    if not db.query(ReadinessConfig).first():
        db.add(ReadinessConfig(
            aptitude_weight=15.0,
            logical_weight=15.0,
            verbal_weight=10.0,
            technical_weight=25.0,
            roadmap_weight=15.0,
            mock_test_weight=20.0,
        ))

    # 3. Seed starter Career Domains, Roadmaps, and Market Trends
    starter_domains = [
        {
            "name": "DevOps & Cloud Engineering",
            "description": "CI/CD pipelines, Linux, Docker, Kubernetes, IaC, and Prometheus/Grafana monitoring.",
            "growth_rate_percent": 26.5,
            "avg_salary_range": "7–18 LPA",
            "steps": [
                "Linux & Shell Scripting Fundamentals",
                "Git, GitHub & Branching Workflows",
                "Docker Containerization & Docker Compose",
                "CI/CD Automation (GitHub Actions / Jenkins)",
                "Monitoring & Observability (Prometheus & Grafana)",
            ],
            "role_title": "Junior DevOps Engineer",
            "demand_index": 92,
            "skills": ["Linux", "Docker", "GitHub Actions", "PostgreSQL", "Prometheus", "Grafana"],
        },
        {
            "name": "Data Analytics",
            "description": "Turning raw business datasets into clear dashboards and actionable decisions.",
            "growth_rate_percent": 23.0,
            "avg_salary_range": "6–14 LPA",
            "steps": [
                "Excel Fundamentals & Pivot Tables",
                "SQL & Database Management (PostgreSQL)",
                "Python for Data Analysis (Pandas & NumPy)",
                "Statistics & Data Visualization",
                "Power BI / Tableau Dashboard Projects",
            ],
            "role_title": "Data Analyst",
            "demand_index": 88,
            "skills": ["Excel", "SQL", "Python", "Statistics", "Power BI", "Tableau"],
        },
        {
            "name": "Software Engineering & Web Dev",
            "description": "Building scalable full-stack web applications, REST APIs, and clean databases.",
            "growth_rate_percent": 21.0,
            "avg_salary_range": "6–16 LPA",
            "steps": [
                "HTML5, Tailwind CSS & Modern JavaScript",
                "Backend REST APIs (Python FastAPI / Node.js)",
                "Relational Databases & SQL Modeling",
                "Authentication, Testing & Security",
                "Capstone Deployment & System Design",
            ],
            "role_title": "Full-Stack Developer",
            "demand_index": 90,
            "skills": ["HTML/CSS", "JavaScript", "Python/FastAPI", "PostgreSQL", "Git", "REST APIs"],
        },
        {
            "name": "Cybersecurity",
            "description": "Securing web applications, networks, cloud workloads, and CI/CD pipelines.",
            "growth_rate_percent": 29.0,
            "avg_salary_range": "7–18 LPA",
            "steps": [
                "Computer Networking & TCP/IP",
                "Linux Security & Identity Management",
                "Web Application Security (OWASP Top 10)",
                "DevSecOps Scanning (Trivy, SonarCloud, Gitleaks)",
                "Incident Response & SIEM Labs",
            ],
            "role_title": "Security Analyst / DevSecOps",
            "demand_index": 94,
            "skills": ["Networking", "Linux", "OWASP Top 10", "Trivy", "SIEM", "Threat Modeling"],
        },
    ]

    for item in starter_domains:
        domain = db.query(CareerDomain).filter(CareerDomain.name == item["name"]).first()
        if not domain:
            domain = CareerDomain(
                name=item["name"],
                description=item["description"],
                growth_rate_percent=item["growth_rate_percent"],
                avg_salary_range=item["avg_salary_range"],
            )
            db.add(domain)
            db.flush()

            for idx, skill in enumerate(item["steps"], start=1):
                db.add(RoadmapStep(
                    domain_id=domain.id,
                    step_order=idx,
                    skill_name=skill,
                    description=f"Master {skill} with hands-on practice and quiz verification.",
                    resources_json=[],
                ))

            db.add(MarketTrend(
                domain_id=domain.id,
                role_title=item["role_title"],
                demand_index=item["demand_index"],
                in_demand_skills_json=item["skills"],
                hiring_trend_json={"2024": item["demand_index"] - 12, "2025": item["demand_index"] - 5, "2026": item["demand_index"]},
                source_name="Learn2Lead Verified Industry Baseline",
            ))

    db.commit()
