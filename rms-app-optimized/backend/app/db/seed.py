"""Idempotent seed: roles, admin + one demo user per role, a business unit, baseline skills,
and the fixed offer template upload to MinIO.

Run:  python -m app.db.seed     (after `alembic upgrade head`)
Safe to run repeatedly — every insert is guarded (ON CONFLICT / WHERE NOT EXISTS).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal, engine

# (role_code, role_name)
ROLES = [
    ("ADMIN", "Administrator"),
    ("HR", "HR Recruiter"),
    ("HIRING_MANAGER", "Hiring Manager"),
    ("BU_HEAD", "Business Unit Head"),
    ("INTERVIEWER", "Interviewer"),
    ("CANDIDATE", "Candidate"),
]

DEMO_PASSWORD = "Passw0rd!23"  # forced strong default for demo logins (change in real deployments)

# (email, full_name, role_code, designation)
DEMO_USERS = [
    ("admin@rms.local", "System Admin", "ADMIN", "Administrator"),
    ("hr@rms.local", "Harriet HR", "HR", "Senior Recruiter"),
    ("hm@rms.local", "Manoj Manager", "HIRING_MANAGER", "Engineering Manager"),
    ("buhead@rms.local", "Bina BU-Head", "BU_HEAD", "BU Head - Engineering"),
    ("interviewer@rms.local", "Ivan Interviewer", "INTERVIEWER", "Principal Engineer"),
    ("candidate@rms.local", "Chandra Candidate", "CANDIDATE", "Applicant"),
]

BUSINESS_UNIT = ("Engineering & Migration", "buhead@rms.local")

# Baseline skills so the SmartLoad demo works before a real Skill Master xlsx is imported (INV-09).
DEFAULT_SKILLS = [
    ("AWS", "Cloud", ["Amazon Web Services", "AWS Cloud"]),
    ("Java", "Language", ["Core Java", "J2EE"]),
    ("Solace", "Messaging", ["Solace PubSub+", "Solace Messaging"]),
    ("Oracle", "Database", ["Oracle DB", "Oracle SQL"]),
    ("TIBCO", "Integration", ["Tibco BW", "Tibco BusinessWorks"]),
    ("Spring Boot", "Framework", ["Springboot", "Spring-Boot"]),
    ("Python", "Language", ["Py"]),
    ("REST APIs", "Integration", ["REST", "RESTful"]),
    ("Microservices", "Architecture", ["Micro-services"]),
    ("Docker", "DevOps", ["Containers"]),
    ("Kubernetes", "DevOps", ["K8s"]),
    ("SQL", "Database", ["Structured Query Language"]),
    ("AWS Step Functions", "Cloud", ["Step Functions"]),
    ("AWS SQS", "Messaging", ["SQS", "Simple Queue Service"]),
]

SEED_DATA_DIR = Path(__file__).resolve().parents[2] / "seed_data"
OFFER_TEMPLATE_FILE = SEED_DATA_DIR / "offer_template_v1.html"
OFFER_TEMPLATE_KEY = "templates/offer_template_v1.html"


async def _seed_roles(session) -> None:
    for code, name in ROLES:
        await session.execute(
            text(
                "INSERT INTO roles (role_code, role_name) VALUES (:c, :n) "
                "ON CONFLICT (role_code) DO NOTHING"
            ),
            {"c": code, "n": name},
        )


async def _seed_users(session) -> None:
    pw_hash = get_password_hash(DEMO_PASSWORD)
    for email, name, role_code, desig in DEMO_USERS:
        # CAST :email to varchar in both spots — asyncpg cannot deduce one type for a param
        # reused as a column value and inside lower() (text).
        await session.execute(
            text(
                "INSERT INTO users (email, password_hash, full_name, role_id, designation) "
                "SELECT CAST(:email AS varchar), :ph, :name, r.role_id, :desig FROM roles r "
                "WHERE r.role_code = :rc "
                "AND NOT EXISTS (SELECT 1 FROM users u WHERE lower(u.email) = lower(CAST(:email AS varchar)))"
            ),
            {"email": email, "ph": pw_hash, "name": name, "desig": desig, "rc": role_code},
        )


async def _seed_business_unit(session) -> None:
    bu_name, head_email = BUSINESS_UNIT
    await session.execute(
        text(
            "INSERT INTO business_units (bu_name, bu_head_user_id) "
            "SELECT :bu, u.user_id FROM users u WHERE lower(u.email) = lower(:email) "
            "ON CONFLICT (bu_name) DO NOTHING"
        ),
        {"bu": bu_name, "email": head_email},
    )


async def _seed_skills(session) -> int:
    """Import from a *.xlsx in seed_data/ if present (cols: skill_name, skill_category, aliases);
    otherwise load DEFAULT_SKILLS. Idempotent by skill_name."""
    skills = DEFAULT_SKILLS
    source = "defaults"
    xlsx = next((p for p in SEED_DATA_DIR.glob("*.xlsx")), None)
    if xlsx is not None:
        try:
            import json

            import openpyxl

            wb = openpyxl.load_workbook(xlsx, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            header = [str(c).strip().lower() if c else "" for c in rows[0]]
            idx = {h: i for i, h in enumerate(header)}
            imported = []
            for r in rows[1:]:
                name = r[idx.get("skill_name", 0)]
                if not name:
                    continue
                cat = r[idx["skill_category"]] if "skill_category" in idx and idx["skill_category"] < len(r) else None
                raw_alias = r[idx["aliases"]] if "aliases" in idx and idx["aliases"] < len(r) else None
                aliases = []
                if raw_alias:
                    try:
                        aliases = json.loads(raw_alias) if str(raw_alias).strip().startswith("[") \
                            else [a.strip() for a in str(raw_alias).split(",") if a.strip()]
                    except Exception:
                        aliases = [str(raw_alias)]
                imported.append((str(name).strip(), str(cat).strip() if cat else None, aliases))
            if imported:
                skills = imported
                source = f"xlsx:{xlsx.name}"
        except Exception as e:  # fall back to defaults, never fail the seed
            print(f"  ! skill xlsx import failed ({e}); using defaults")

    import json

    for name, category, aliases in skills:
        await session.execute(
            text(
                "INSERT INTO skill_master (skill_name, skill_category, aliases) "
                "VALUES (:n, :c, CAST(:a AS jsonb)) ON CONFLICT (skill_name) DO NOTHING"
            ),
            {"n": name, "c": category, "a": json.dumps(aliases)},
        )
    print(f"  skills source: {source} ({len(skills)} rows)")
    return len(skills)


def _upload_offer_template() -> None:
    """Best-effort upload of the fixed offer template to MinIO (INV-10). Never fails the seed."""
    if not settings.MINIO_ENDPOINT or not settings.MINIO_BUCKET:
        print("  ! MinIO not configured; skipping offer template upload")
        return
    if not OFFER_TEMPLATE_FILE.exists():
        print(f"  ! offer template not found at {OFFER_TEMPLATE_FILE}; skipping")
        return
    try:
        from minio import Minio

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        data = OFFER_TEMPLATE_FILE.read_bytes()
        import io

        # Always (re)upload so template edits ship on re-seed (idempotent by content).
        client.put_object(
            settings.MINIO_BUCKET, OFFER_TEMPLATE_KEY, io.BytesIO(data), length=len(data),
            content_type="text/html",
        )
        print(f"  uploaded offer template -> {settings.MINIO_BUCKET}/{OFFER_TEMPLATE_KEY}")
    except Exception as e:
        print(f"  ! offer template upload failed ({e}); continuing")


async def main() -> None:
    print(f"Seeding schema '{settings.PG_SCHEMA}' ...")
    async with SessionLocal() as session:
        await _seed_roles(session)
        await _seed_users(session)
        await _seed_business_unit(session)
        await _seed_skills(session)
        await session.commit()
    _upload_offer_template()
    await engine.dispose()

    print("\nSeed complete. Demo credentials (password is identical for all):")
    print(f"  password: {DEMO_PASSWORD}")
    for email, name, role_code, _ in DEMO_USERS:
        print(f"  {role_code:<15} {email:<24} ({name})")


if __name__ == "__main__":
    asyncio.run(main())
