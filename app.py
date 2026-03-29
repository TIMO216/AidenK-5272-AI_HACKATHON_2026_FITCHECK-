import json
import os
from functools import wraps

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from fitcheck.ai import FitCheckAI
from fitcheck.scoring import analyze_fit
from fitcheck.storage import (
    create_fitcheck,
    get_fitcheck,
    get_or_create_user,
    get_screener,
    get_user,
    init_db,
    list_fitchecks,
    save_screener,
)


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fitcheck-dev-secret")
init_db()


SAMPLE_RESUME = """Jordan Lee
Computer Science Student

EDUCATION
State University, B.S. Computer Science, Expected 2027

EXPERIENCE
Software Engineering Intern, Campus Labs
- Built a Flask and PostgreSQL dashboard used by 400+ student mentors to track appointments.
- Wrote Python scripts to clean reporting data, cutting weekly manual work by 6 hours.
- Partnered with a product manager and presented sprint demos to stakeholders.

PROJECTS
Career Compass
- Created a React and Node.js web app that scored resumes against internship job descriptions.
- Designed REST APIs, wrote unit tests, and deployed the app on Render.
- Improved resume parsing accuracy by 18% using rule-based extraction.

SKILLS
Python, Flask, SQL, PostgreSQL, JavaScript, React, REST APIs, Git, unit testing
"""


SAMPLE_JOB_DESCRIPTION = """Software Engineering Intern

We are looking for a student to help build internal tools for our advising team.
Responsibilities:
- Build Python and Flask services and maintain REST APIs.
- Work with SQL and PostgreSQL data models.
- Collaborate with product managers and designers.
- Write tests and document technical decisions.

Preferred:
- Experience shipping student projects or internship work.
- Familiarity with analytics dashboards and data pipelines.
- Strong written communication and stakeholder presentation skills.
"""


def fit_band_for_score(score: int) -> str:
    if score >= 80:
        return "Strong Fit"
    if score >= 60:
        return "Moderate Fit"
    return "Stretch"


def get_fitcheck_ai() -> FitCheckAI:
    return FitCheckAI()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user(int(user_id))


def current_screener():
    user = current_user()
    if not user:
        return None
    return get_screener(int(user["id"]))


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def screener_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login"))
        if current_screener() is None:
            return redirect(url_for("screener"))
        return view_func(*args, **kwargs)

    return wrapped_view


def infer_title(job_description: str) -> tuple[str, str]:
    lines = [line.strip() for line in job_description.splitlines() if line.strip()]
    title = lines[0] if lines else "Untitled FitCheck"
    company_hint = ""
    if len(lines) > 1 and len(lines[1]) < 48:
        company_hint = lines[1]
    title = title[:80]
    company_hint = company_hint[:60]
    return title, company_hint


def plain_text_screener(screener_row) -> str:
    if screener_row is None:
        return ""
    return "\n".join(
        [
            f"University: {screener_row['university']}",
            f"Major: {screener_row['major']}",
            f"Year: {screener_row['year']}",
            f"Career goals: {screener_row['career_goals']}",
            f"What they feel unsure about: {screener_row['unsure_about']}",
        ]
    )


def run_fitcheck_analysis(
    *,
    screener_text: str,
    resume_text: str,
    job_description: str,
    experience_level: str,
    job_type: str,
) -> dict:
    fitcheck_ai = get_fitcheck_ai()
    result = analyze_fit(
        resume_text,
        job_description,
        experience_level=experience_level,
        job_type=job_type,
    )
    fit_band = fit_band_for_score(result["overall_score"])
    result["fit_band"] = fit_band

    ai_summary = fitcheck_ai.generate_summary(
        final_score=result["overall_score"],
        fit_band=fit_band,
        screener_text=screener_text,
        experience_level=experience_level,
        top_gaps=result["top_gaps"],
    )
    if ai_summary:
        result["coach_summary"] = ai_summary

    ai_suggestions = fitcheck_ai.generate_suggestions(
        screener_text=screener_text,
        job_description=job_description,
        experience_level=experience_level,
        job_type=job_type,
        top_gaps=result["top_gaps"],
    )
    if ai_suggestions:
        result["suggestions"] = [
            {
                "title": item["title"],
                "body": item["body"],
                "resource": item["resource"],
                "priority": "High",
            }
            for item in ai_suggestions
        ]

    return result


@app.route("/")
def home():
    user = current_user()
    if user is None:
        return redirect(url_for("login"))
    if current_screener() is None:
        return redirect(url_for("screener"))
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        if not full_name or not email:
            flash("Enter your name and email to open your FitCheck workspace.", "error")
            return render_template("login.html")

        user = get_or_create_user(full_name, email)
        session["user_id"] = int(user["id"])
        if get_screener(int(user["id"])) is None:
            return redirect(url_for("screener"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/screener", methods=["GET", "POST"])
@login_required
def screener():
    existing = current_screener()
    user = current_user()

    if request.method == "POST":
        save_screener(
            int(user["id"]),
            university=request.form.get("university", ""),
            major=request.form.get("major", ""),
            year=request.form.get("year", ""),
            career_goals=request.form.get("career_goals", ""),
            unsure_about=request.form.get("unsure_about", ""),
        )
        return redirect(url_for("dashboard"))

    return render_template("screener.html", screener=existing)


@app.route("/dashboard")
@screener_required
def dashboard():
    user = current_user()
    screener = current_screener()
    fitchecks = list_fitchecks(int(user["id"]))

    cards = []
    for item in fitchecks:
        result = json.loads(item["result_json"])
        cards.append(
            {
                "id": item["id"],
                "title": item["title"],
                "company_hint": item["company_hint"],
                "experience_level": item["experience_level"],
                "job_type": item["job_type"],
                "created_at": item["created_at"],
                "score": result.get("overall_score", 0),
                "fit_band": result.get("fit_band", fit_band_for_score(result.get("overall_score", 0))),
                "top_gaps": result.get("top_gaps", []),
            }
        )

    return render_template(
        "dashboard.html",
        user=user,
        screener=screener,
        fitchecks=cards,
    )


@app.route("/fitchecks/new", methods=["GET", "POST"])
@screener_required
def new_fitcheck():
    screener = current_screener()
    resume_text = SAMPLE_RESUME
    job_description = SAMPLE_JOB_DESCRIPTION
    job_type = "Software and Engineering"

    if request.method == "POST":
        resume_text = request.form.get("resume_text", "").strip()
        job_description = request.form.get("job_description", "").strip()
        job_type = request.form.get("job_type", job_type)
        experience_level = screener["year"]

        if not resume_text or not job_description:
            flash("Paste both a resume and a job description before running FitCheck.", "error")
            return render_template(
                "fitcheck_form.html",
                screener=screener,
                resume_text=resume_text,
                job_description=job_description,
                job_type=job_type,
            )

        result = run_fitcheck_analysis(
            screener_text=plain_text_screener(screener),
            resume_text=resume_text,
            job_description=job_description,
            experience_level=experience_level,
            job_type=job_type,
        )
        title, company_hint = infer_title(job_description)
        fitcheck_id = create_fitcheck(
            int(current_user()["id"]),
            title=title,
            company_hint=company_hint,
            experience_level=experience_level,
            job_type=job_type,
            resume_text=resume_text,
            job_description=job_description,
            result=result,
        )
        return redirect(url_for("fitcheck_detail", fitcheck_id=fitcheck_id))

    return render_template(
        "fitcheck_form.html",
        screener=screener,
        resume_text=resume_text,
        job_description=job_description,
        job_type=job_type,
    )


@app.route("/fitchecks/<int:fitcheck_id>")
@screener_required
def fitcheck_detail(fitcheck_id: int):
    payload = get_fitcheck(int(current_user()["id"]), fitcheck_id)
    if payload is None:
        flash("That FitCheck could not be found.", "error")
        return redirect(url_for("dashboard"))

    return render_template(
        "fitcheck_detail.html",
        fitcheck=payload,
        result=payload["result"],
        experience_level=payload["experience_level"],
        job_type=payload["job_type"],
        ai_enabled=get_fitcheck_ai().enabled,
    )


@app.post("/api/chat")
@screener_required
def chat():
    fitcheck_ai = get_fitcheck_ai()
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    context = payload.get("context") or {}

    if not question:
        return jsonify({"error": "Question is required."}), 400

    answer = fitcheck_ai.answer_chat(
        question=question,
        score=int(context.get("score", 0)),
        fit_band=context.get("fit_band", "Stretch"),
        experience_level=context.get("experience_level", "Junior"),
        job_type=context.get("job_type", "Other"),
        gaps=context.get("gaps", []),
    )
    return jsonify({"answer": answer})


@app.context_processor
def inject_layout_context():
    return {
        "current_user": current_user(),
        "current_screener": current_screener(),
    }


if __name__ == "__main__":
    app.run(debug=True)
