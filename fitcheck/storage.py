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
            target_roles TEXT,
            interests TEXT,
            certifications_considering TEXT,
            personality_style TEXT,
            collaboration_style TEXT,
            task_style TEXT,
            confidence_level TEXT,
            confidence_environments TEXT,
            strengths TEXT,
            concerns TEXT,
            guidance_needed TEXT,
            unsure_about TEXT,
            time_constraints TEXT,
            work_commitments TEXT,
            commute_constraints TEXT,
            access_constraints TEXT,
            personal_boundaries TEXT,
            energy_limits TEXT,
            semester_goal TEXT,
            long_term_goal TEXT,
            already_tried TEXT,
            avoiding TEXT,
            proud_of TEXT,
            progress_definition TEXT,
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
    ensure_column(cursor, "pathway_profiles", "target_roles", "TEXT")
    ensure_column(cursor, "pathway_profiles", "interests", "TEXT")
    ensure_column(cursor, "pathway_profiles", "certifications_considering", "TEXT")
    ensure_column(cursor, "pathway_profiles", "personality_style", "TEXT")
    ensure_column(cursor, "pathway_profiles", "collaboration_style", "TEXT")
    ensure_column(cursor, "pathway_profiles", "task_style", "TEXT")
    ensure_column(cursor, "pathway_profiles", "confidence_level", "TEXT")
    ensure_column(cursor, "pathway_profiles", "confidence_environments", "TEXT")
    ensure_column(cursor, "pathway_profiles", "strengths", "TEXT")
    ensure_column(cursor, "pathway_profiles", "concerns", "TEXT")
    ensure_column(cursor, "pathway_profiles", "guidance_needed", "TEXT")
    ensure_column(cursor, "pathway_profiles", "unsure_about", "TEXT")
    ensure_column(cursor, "pathway_profiles", "time_constraints", "TEXT")
    ensure_column(cursor, "pathway_profiles", "work_commitments", "TEXT")
    ensure_column(cursor, "pathway_profiles", "commute_constraints", "TEXT")
    ensure_column(cursor, "pathway_profiles", "access_constraints", "TEXT")
    ensure_column(cursor, "pathway_profiles", "personal_boundaries", "TEXT")
    ensure_column(cursor, "pathway_profiles", "energy_limits", "TEXT")
    ensure_column(cursor, "pathway_profiles", "semester_goal", "TEXT")
    ensure_column(cursor, "pathway_profiles", "long_term_goal", "TEXT")
    ensure_column(cursor, "pathway_profiles", "already_tried", "TEXT")
    ensure_column(cursor, "pathway_profiles", "avoiding", "TEXT")
    ensure_column(cursor, "pathway_profiles", "proud_of", "TEXT")
    ensure_column(cursor, "pathway_profiles", "progress_definition", "TEXT")
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
            unsure_about,
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
    target_roles: str,
    interests: str,
    certifications_considering: str,
    personality_style: str,
    collaboration_style: str,
    task_style: str,
    confidence_level: str,
    confidence_environments: str,
    strengths: str,
    concerns: str,
    guidance_needed: str,
    unsure_about: str,
    time_constraints: str,
    work_commitments: str,
    commute_constraints: str,
    access_constraints: str,
    personal_boundaries: str,
    energy_limits: str,
    semester_goal: str,
    long_term_goal: str,
    already_tried: str,
    avoiding: str,
    proud_of: str,
    progress_definition: str,
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
            target_roles,
            interests,
            certifications_considering,
            personality_style,
            collaboration_style,
            task_style,
            confidence_level,
            confidence_environments,
            strengths,
            concerns,
            guidance_needed,
            unsure_about,
            time_constraints,
            work_commitments,
            commute_constraints,
            access_constraints,
            personal_boundaries,
            energy_limits,
            semester_goal,
            long_term_goal,
            already_tried,
            avoiding,
            proud_of,
            progress_definition,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            university = excluded.university,
            major = excluded.major,
            year = excluded.year,
            target_roles = excluded.target_roles,
            interests = excluded.interests,
            certifications_considering = excluded.certifications_considering,
            personality_style = excluded.personality_style,
            collaboration_style = excluded.collaboration_style,
            task_style = excluded.task_style,
            confidence_level = excluded.confidence_level,
            confidence_environments = excluded.confidence_environments,
            strengths = excluded.strengths,
            concerns = excluded.concerns,
            guidance_needed = excluded.guidance_needed,
            unsure_about = excluded.unsure_about,
            time_constraints = excluded.time_constraints,
            work_commitments = excluded.work_commitments,
            commute_constraints = excluded.commute_constraints,
            access_constraints = excluded.access_constraints,
            personal_boundaries = excluded.personal_boundaries,
            energy_limits = excluded.energy_limits,
            semester_goal = excluded.semester_goal,
            long_term_goal = excluded.long_term_goal,
            already_tried = excluded.already_tried,
            avoiding = excluded.avoiding,
            proud_of = excluded.proud_of,
            progress_definition = excluded.progress_definition,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            university.strip(),
            major.strip(),
            year.strip(),
            target_roles.strip(),
            interests.strip(),
            certifications_considering.strip(),
            personality_style.strip(),
            collaboration_style.strip(),
            task_style.strip(),
            confidence_level.strip(),
            confidence_environments.strip(),
            strengths.strip(),
            concerns.strip(),
            guidance_needed.strip(),
            unsure_about.strip(),
            time_constraints.strip(),
            work_commitments.strip(),
            commute_constraints.strip(),
            access_constraints.strip(),
            personal_boundaries.strip(),
            energy_limits.strip(),
            semester_goal.strip(),
            long_term_goal.strip(),
            already_tried.strip(),
            avoiding.strip(),
            proud_of.strip(),
            progress_definition.strip(),
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
        SELECT id, title, company_hint, experience_level, job_type, created_at, result_json
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
