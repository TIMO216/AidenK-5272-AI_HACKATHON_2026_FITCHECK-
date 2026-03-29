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
        CREATE TABLE IF NOT EXISTS screeners (
            user_id INTEGER PRIMARY KEY,
            university TEXT,
            major TEXT,
            year TEXT,
            career_goals TEXT,
            unsure_about TEXT,
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
            title TEXT NOT NULL,
            company_hint TEXT,
            experience_level TEXT,
            job_type TEXT,
            resume_text TEXT NOT NULL,
            job_description TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    connection.commit()
    connection.close()


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


def save_screener(
    user_id: int,
    *,
    university: str,
    major: str,
    year: str,
    career_goals: str,
    unsure_about: str,
) -> None:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO screeners (user_id, university, major, year, career_goals, unsure_about, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            university = excluded.university,
            major = excluded.major,
            year = excluded.year,
            career_goals = excluded.career_goals,
            unsure_about = excluded.unsure_about,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, university.strip(), major.strip(), year.strip(), career_goals.strip(), unsure_about.strip()),
    )
    connection.commit()
    connection.close()


def get_screener(user_id: int) -> Optional[sqlite3.Row]:
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM screeners WHERE user_id = ?", (user_id,))
    screener = cursor.fetchone()
    connection.close()
    return screener


def create_fitcheck(
    user_id: int,
    *,
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
            title,
            company_hint,
            experience_level,
            job_type,
            resume_text,
            job_description,
            result_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
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
