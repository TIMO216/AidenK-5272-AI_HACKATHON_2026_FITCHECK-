import json
import sqlite3
from pathlib import Path
from typing import Any, Optional


DB_PATH = Path(__file__).resolve().parent.parent / "fitcheck.db"


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pathway_profiles (
            user_id INTEGER PRIMARY KEY,
            university TEXT,
            major TEXT,
            year TEXT,
            gpa_range TEXT,
            personality_style TEXT,
            interests TEXT,
            certifications_considering TEXT,
            target_roles TEXT,
            target_organizations TEXT,
            timeline TEXT,
            opportunity_type TEXT,
            mentor_status TEXT,
            involvement_status TEXT,
            linkedin_status TEXT,
            cold_email_status TEXT,
            outreach_comfort TEXT,
            email_signature_status TEXT,
            career_fair_status TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fitchecks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            parent_fitcheck_id INTEGER,
            title TEXT NOT NULL,
            company_hint TEXT,
            experience_level TEXT,
            job_type TEXT,
            resume_text TEXT NOT NULL,
            job_description TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(parent_fitcheck_id) REFERENCES fitchecks(id)
        )
        """
    )

    ensure_column(cursor, "fitchecks", "parent_fitcheck_id", "INTEGER")
    ensure_column(cursor, "pathway_profiles", "gpa_range", "TEXT")
    ensure_column(cursor, "pathway_profiles", "target_roles", "TEXT")
    ensure_column(cursor, "pathway_profiles", "interests", "TEXT")
    ensure_column(cursor, "pathway_profiles", "certifications_considering", "TEXT")
    ensure_column(cursor, "pathway_profiles", "personality_style", "TEXT")
    ensure_column(cursor, "pathway_profiles", "target_organizations", "TEXT")
    ensure_column(cursor, "pathway_profiles", "timeline", "TEXT")
    ensure_column(cursor, "pathway_profiles", "opportunity_type", "TEXT")
    ensure_column(cursor, "pathway_profiles", "mentor_status", "TEXT")
    ensure_column(cursor, "pathway_profiles", "involvement_status", "TEXT")
    ensure_column(cursor, "pathway_profiles", "linkedin_status", "TEXT")
    ensure_column(cursor, "pathway_profiles", "cold_email_status", "TEXT")
    ensure_column(cursor, "pathway_profiles", "outreach_comfort", "TEXT")
    ensure_column(cursor, "pathway_profiles", "email_signature_status", "TEXT")
    ensure_column(cursor, "pathway_profiles", "career_fair_status", "TEXT")
    migrate_legacy_pathway_profile_data(cursor)

    connection.commit()
    connection.close()


def ensure_column(cursor: sqlite3.Cursor, table_name: str, column_name: str, definition: str) -> None:
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def migrate_legacy_pathway_profile_data(cursor: sqlite3.Cursor) -> None:
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'screeners'")
    if cursor.fetchone() is None:
        return

    cursor.execute(
        """
        INSERT INTO pathway_profiles (
            user_id,
            university,
            major,
            year,
            target_roles,
            interests,
            updated_at
        )
        SELECT
            user_id,
            university,
            major,
            year,
            career_goals,
            unsure_about,
            updated_at
        FROM screeners
        WHERE user_id NOT IN (SELECT user_id FROM pathway_profiles)
        """
    )


def get_or_create_user(full_name: str, email: str) -> sqlite3.Row:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    user = cursor.fetchone()

    if user is None:
        cursor.execute(
            "INSERT INTO users (full_name, email) VALUES (?, ?)",
            (full_name.strip(), email.lower().strip()),
        )
        connection.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,))
        user = cursor.fetchone()

    connection.close()
    return user


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    connection.close()
    return user


def save_pathway_profile(
    user_id: int,
    *,
    university: str,
    major: str,
    year: str,
    gpa_range: str,
    target_roles: str,
    interests: str,
    certifications_considering: str,
    personality_style: str,
    target_organizations: str,
    timeline: str,
    opportunity_type: str,
    mentor_status: str,
    involvement_status: str,
    linkedin_status: str,
    cold_email_status: str,
    outreach_comfort: str,
    email_signature_status: str,
    career_fair_status: str,
) -> None:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO pathway_profiles (
            user_id,
            university,
            major,
            year,
            gpa_range,
            personality_style,
            interests,
            certifications_considering,
            target_roles,
            target_organizations,
            timeline,
            opportunity_type,
            mentor_status,
            involvement_status,
            linkedin_status,
            cold_email_status,
            outreach_comfort,
            email_signature_status,
            career_fair_status,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            university = excluded.university,
            major = excluded.major,
            year = excluded.year,
            gpa_range = excluded.gpa_range,
            personality_style = excluded.personality_style,
            interests = excluded.interests,
            certifications_considering = excluded.certifications_considering,
            target_roles = excluded.target_roles,
            target_organizations = excluded.target_organizations,
            timeline = excluded.timeline,
            opportunity_type = excluded.opportunity_type,
            mentor_status = excluded.mentor_status,
            involvement_status = excluded.involvement_status,
            linkedin_status = excluded.linkedin_status,
            cold_email_status = excluded.cold_email_status,
            outreach_comfort = excluded.outreach_comfort,
            email_signature_status = excluded.email_signature_status,
            career_fair_status = excluded.career_fair_status,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            university.strip(),
            major.strip(),
            year.strip(),
            gpa_range.strip(),
            personality_style.strip(),
            interests.strip(),
            certifications_considering.strip(),
            target_roles.strip(),
            target_organizations.strip(),
            timeline.strip(),
            opportunity_type.strip(),
            mentor_status.strip(),
            involvement_status.strip(),
            linkedin_status.strip(),
            cold_email_status.strip(),
            outreach_comfort.strip(),
            email_signature_status.strip(),
            career_fair_status.strip(),
        ),
    )
    connection.commit()
    connection.close()


def get_pathway_profile(user_id: int) -> Optional[sqlite3.Row]:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM pathway_profiles WHERE user_id = ?", (user_id,))
    pathway_profile = cursor.fetchone()
    connection.close()
    return pathway_profile


def create_fitcheck(
    user_id: int,
    *,
    parent_fitcheck_id: Optional[int] = None,
    title: str,
    company_hint: str,
    experience_level: str,
    job_type: str,
    resume_text: str,
    job_description: str,
    result: dict[str, Any],
) -> int:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO fitchecks (
            user_id,
            parent_fitcheck_id,
            title,
            company_hint,
            experience_level,
            job_type,
            resume_text,
            job_description,
            result_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            parent_fitcheck_id,
            title.strip(),
            company_hint.strip(),
            experience_level.strip(),
            job_type.strip(),
            resume_text,
            job_description,
            json.dumps(result),
        ),
    )
    connection.commit()
    fitcheck_id = cursor.lastrowid
    connection.close()
    return int(fitcheck_id)


def list_fitchecks(user_id: int) -> list[sqlite3.Row]:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, title, company_hint, experience_level, job_type, created_at, result_json, job_description
        FROM fitchecks
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


def get_fitcheck(user_id: int, fitcheck_id: int) -> Optional[dict[str, Any]]:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM fitchecks
        WHERE id = ? AND user_id = ?
        """,
        (fitcheck_id, user_id),
    )
    row = cursor.fetchone()
    connection.close()
    if row is None:
        return None

    payload = dict(row)
    payload["result"] = json.loads(payload["result_json"])
    return payload


def delete_fitcheck(user_id: int, fitcheck_id: int) -> None:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM fitchecks WHERE id = ? AND user_id = ?",
        (fitcheck_id, user_id),
    )
    connection.commit()
    connection.close()
