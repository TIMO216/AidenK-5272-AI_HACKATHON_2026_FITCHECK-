import json
import os
from functools import wraps

import pdfplumber
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from fitcheck.ai import FitCheckAI
from fitcheck.review import build_resubmit_comparison
from fitcheck.scoring import analyze_fit
from fitcheck.storage import (
    create_fitcheck,
    delete_fitcheck,
    get_fitcheck,
    get_or_create_user,
    get_pathway_profile,
    get_user,
    init_db,
    list_fitchecks,
    save_pathway_profile,
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


def extract_resume_text_from_pdf(uploaded_file) -> str:
    with pdfplumber.open(uploaded_file) as pdf:
        pages = [(page.extract_text() or "").strip() for page in pdf.pages]
    return "\n".join(page for page in pages if page).strip()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user(int(user_id))


def current_pathway_profile():
    user = current_user()
    if not user:
        return None
    return get_pathway_profile(int(user["id"]))


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def pathway_profile_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login"))
        if current_pathway_profile() is None:
            return redirect(url_for("pathway_profile"))
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


def plain_text_pathway_profile(pathway_profile_row) -> str:
    if pathway_profile_row is None:
        return ""
    fields = [
        ("University", pathway_profile_row["university"]),
        ("Major", pathway_profile_row["major"]),
        ("Year", pathway_profile_row["year"]),
        ("Target roles", pathway_profile_row["target_roles"]),
        ("Interests", pathway_profile_row["interests"]),
        ("Certifications considering", pathway_profile_row["certifications_considering"]),
        ("Personality", pathway_profile_row["personality_style"]),
        ("Work style", pathway_profile_row["collaboration_style"]),
        ("Task style", pathway_profile_row["task_style"]),
        ("Confidence level", pathway_profile_row["confidence_level"]),
        ("Where they feel confident", pathway_profile_row["confidence_environments"]),
        ("Strengths", pathway_profile_row["strengths"]),
        ("Concerns", pathway_profile_row["concerns"]),
        ("What they wish they had guidance on", pathway_profile_row["guidance_needed"]),
        ("What they are unsure about", pathway_profile_row["unsure_about"]),
        ("Time constraints", pathway_profile_row["time_constraints"]),
        ("Work commitments", pathway_profile_row["work_commitments"]),
        ("Commute constraints", pathway_profile_row["commute_constraints"]),
        ("Access constraints", pathway_profile_row["access_constraints"]),
        ("Personal boundaries", pathway_profile_row["personal_boundaries"]),
        ("Energy or workload limits", pathway_profile_row["energy_limits"]),
        ("What they want this semester", pathway_profile_row["semester_goal"]),
        ("What they want long-term", pathway_profile_row["long_term_goal"]),
        ("What they have already tried", pathway_profile_row["already_tried"]),
        ("What they are avoiding", pathway_profile_row["avoiding"]),
        ("What they are proud of", pathway_profile_row["proud_of"]),
        ("What progress looks like", pathway_profile_row["progress_definition"]),
    ]
    return "\n".join(
        f"{label}: {value}" for label, value in fields if value
    )


def green_light_tips(job_type: str) -> list[str]:
    tips_by_job_type = {
        "Data and Analytics": [
            "Apply now and be ready to talk through one analysis from start to finish.",
            "Bring one clean project or notebook link that shows how you think with data.",
            "Practice explaining your findings in plain English, not just tool names.",
        ],
        "Software and Engineering": [
            "Apply now and be ready to explain one project decision clearly in interviews.",
            "Keep one code sample or project walkthrough ready so you can talk through how it works.",
            "Focus on clear, calm storytelling about what you built and why it mattered.",
        ],
        "Research and Science": [
            "Apply now and be ready to explain one method, one result, and one thing you learned.",
            "Reach out to one professor or mentor who can vouch for how you work.",
            "Keep a short project or lab summary ready in case someone asks about your process.",
        ],
    }
    return tips_by_job_type.get(
        job_type,
        [
            "Apply now and be ready to explain your strongest example clearly.",
            "Keep one focused story ready about how you solved a real problem.",
            "Let your confidence come from real preparation, not endless last-minute edits.",
        ],
    )


def apply_green_light_state(result: dict, job_type: str) -> dict:
    result["top_gaps"] = []
    result["suggestions"] = []
    result["green_light"] = {
        "message": "You are competitive for this role.",
        "body": "This is the point where FitCheck stops critiquing and tells you to go apply.",
        "tips": green_light_tips(job_type),
    }
    return result


def fallback_resubmit_suggestions(remaining_gaps: list[str], job_type: str) -> list[dict]:
    suggestions = []
    for gap in remaining_gaps[:2]:
        suggestions.append(
            {
                "title": gap,
                "body": f"This is still one of the last meaningful things holding you back for {job_type.lower()} roles. Keep your next move focused and realistic.",
                "resource": "Pick one concrete action this week that gives you stronger proof here without overloading yourself.",
                "priority": "High",
            }
        )
    return suggestions


def run_fitcheck_analysis(
    *,
    pathway_profile_text: str,
    resume_text: str,
    job_description: str,
    experience_level: str,
    job_type: str,
    previous_fitcheck: dict | None = None,
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

    resubmit_context = None
    if previous_fitcheck is not None:
        comparison = build_resubmit_comparison(previous_fitcheck, result, resume_text)
        result["comparison"] = comparison
        result["top_gaps"] = comparison["whats_left"]
        resubmit_context = comparison

    ai_summary = fitcheck_ai.generate_summary(
        final_score=result["overall_score"],
        fit_band=fit_band,
        pathway_profile_text=pathway_profile_text,
        experience_level=experience_level,
        top_gaps=result["top_gaps"],
        resubmit_context=resubmit_context,
    )
    if ai_summary:
        result["coach_summary"] = ai_summary

    if previous_fitcheck is not None and result["overall_score"] >= 80:
        result = apply_green_light_state(result, job_type)
    else:
        ai_suggestions = fitcheck_ai.generate_suggestions(
            pathway_profile_text=pathway_profile_text,
            job_description=job_description,
            experience_level=experience_level,
            job_type=job_type,
            top_gaps=result["top_gaps"],
            resubmit_context=resubmit_context,
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
        elif previous_fitcheck is not None:
            result["suggestions"] = fallback_resubmit_suggestions(result["top_gaps"], job_type)

    return result


@app.route("/")
def home():
    user = current_user()
    if user is None:
        return redirect(url_for("login"))
    if current_pathway_profile() is None:
        return redirect(url_for("pathway_profile"))
    return redirect(url_for("dashboard"))


@app.route("/home")
@pathway_profile_required
def workspace_home():
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    errors = {}
    form_values = {"full_name": "", "email": ""}

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        form_values = {"full_name": full_name, "email": email}

        if len(full_name.split()) < 2:
            errors["full_name"] = "Enter your first and last name."
        if "@" not in email:
            errors["email"] = "Enter a valid school email."
        elif not email.lower().endswith(".edu"):
            errors["email"] = "Use your .edu email."

        if errors:
            return render_template("login.html", errors=errors, form_values=form_values)

        user = get_or_create_user(full_name, email)
        session["user_id"] = int(user["id"])
        session["name"] = full_name
        session["email"] = email.lower()
        if get_pathway_profile(int(user["id"])) is None:
            return redirect(url_for("pathway_profile"))
        return redirect(url_for("dashboard"))

    return render_template("login.html", errors=errors, form_values=form_values)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/pathway-profile", methods=["GET", "POST"])
@login_required
def pathway_profile():
    existing = current_pathway_profile()
    user = current_user()

    if request.method == "POST":
        save_pathway_profile(
            int(user["id"]),
            university=request.form.get("university", ""),
            major=request.form.get("major", ""),
            year=request.form.get("year", ""),
            target_roles=request.form.get("target_roles", ""),
            interests=request.form.get("interests", ""),
            certifications_considering=request.form.get("certifications_considering", ""),
            personality_style=request.form.get("personality_style", ""),
            collaboration_style=request.form.get("collaboration_style", ""),
            task_style=request.form.get("task_style", ""),
            confidence_level=request.form.get("confidence_level", ""),
            confidence_environments=request.form.get("confidence_environments", ""),
            strengths=request.form.get("strengths", ""),
            concerns=request.form.get("concerns", ""),
            guidance_needed=request.form.get("guidance_needed", ""),
            unsure_about=request.form.get("unsure_about", ""),
            time_constraints=request.form.get("time_constraints", ""),
            work_commitments=request.form.get("work_commitments", ""),
            commute_constraints=request.form.get("commute_constraints", ""),
            access_constraints=request.form.get("access_constraints", ""),
            personal_boundaries=request.form.get("personal_boundaries", ""),
            energy_limits=request.form.get("energy_limits", ""),
            semester_goal=request.form.get("semester_goal", ""),
            long_term_goal=request.form.get("long_term_goal", ""),
            already_tried=request.form.get("already_tried", ""),
            avoiding=request.form.get("avoiding", ""),
            proud_of=request.form.get("proud_of", ""),
            progress_definition=request.form.get("progress_definition", ""),
        )
        return redirect(url_for("dashboard"))

    return render_template("pathway_profile.html", pathway_profile=existing)

@app.route("/dashboard")
@pathway_profile_required
def dashboard():
    user = current_user()
    pathway_profile = current_pathway_profile()
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
        pathway_profile=pathway_profile,
        fitchecks=cards,
    )


@app.route("/new", methods=["GET", "POST"])
@pathway_profile_required
def new_fitcheck_alias():
    return new_fitcheck()


@app.route("/fitchecks/new", methods=["GET", "POST"])
@pathway_profile_required
def new_fitcheck():
    pathway_profile = current_pathway_profile()
    resume_text = ""
    job_description = ""
    job_type = "Software and Engineering"

    if request.method == "POST":
        resume_text = request.form.get("resume_text", "").strip()
        job_description = request.form.get("job_description", "").strip()
        job_type = request.form.get("job_type", job_type)
        experience_level = pathway_profile["year"]
        uploaded_resume = request.files.get("resume_pdf")

        if uploaded_resume and uploaded_resume.filename:
            try:
                extracted_text = extract_resume_text_from_pdf(uploaded_resume)
                if extracted_text:
                    resume_text = extracted_text
                else:
                    flash("We couldn't read this PDF. Please paste your resume instead.", "error")
                    return render_template(
                        "fitcheck_form.html",
                        pathway_profile=pathway_profile,
                        resume_text=request.form.get("resume_text", ""),
                        job_description=job_description,
                        job_type=job_type,
                    )
            except Exception:
                flash("We couldn't read this PDF. Please paste your resume instead.", "error")
                return render_template(
                    "fitcheck_form.html",
                    pathway_profile=pathway_profile,
                    resume_text=request.form.get("resume_text", ""),
                    job_description=job_description,
                    job_type=job_type,
                )

        if not resume_text or not job_description:
            flash("Add your resume and the job description before you run FitCheck.", "error")
            return render_template(
                "fitcheck_form.html",
                pathway_profile=pathway_profile,
                resume_text=resume_text,
                job_description=job_description,
                job_type=job_type,
            )

        result = run_fitcheck_analysis(
            pathway_profile_text=plain_text_pathway_profile(pathway_profile),
            resume_text=resume_text,
            job_description=job_description,
            experience_level=experience_level,
            job_type=job_type,
        )
        title, company_hint = infer_title(job_description)
        fitcheck_id = create_fitcheck(
            int(current_user()["id"]),
            parent_fitcheck_id=None,
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
        pathway_profile=pathway_profile,
        resume_text=resume_text,
        job_description=job_description,
        job_type=job_type,
    )


@app.route("/delete/<int:fitcheck_id>", methods=["POST"])
@pathway_profile_required
def delete_fitcheck_route(fitcheck_id: int):
    delete_fitcheck(int(current_user()["id"]), fitcheck_id)
    return redirect(url_for("workspace_home"))


@app.route("/fitchecks/<int:fitcheck_id>")
@pathway_profile_required
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


@app.route("/fitchecks/<int:fitcheck_id>/resubmit", methods=["POST"])
@pathway_profile_required
def resubmit_fitcheck(fitcheck_id: int):
    previous_fitcheck = get_fitcheck(int(current_user()["id"]), fitcheck_id)
    if previous_fitcheck is None:
        flash("That FitCheck could not be found.", "error")
        return redirect(url_for("dashboard"))

    pathway_profile = current_pathway_profile()
    resume_text = request.form.get("resume_text", "").strip()
    uploaded_resume = request.files.get("resume_pdf")

    if uploaded_resume and uploaded_resume.filename:
        try:
            extracted_text = extract_resume_text_from_pdf(uploaded_resume)
            if extracted_text:
                resume_text = extracted_text
            else:
                flash("We couldn't read this PDF. Please paste your resume instead.", "error")
                return redirect(url_for("fitcheck_detail", fitcheck_id=fitcheck_id))
        except Exception:
            flash("We couldn't read this PDF. Please paste your resume instead.", "error")
            return redirect(url_for("fitcheck_detail", fitcheck_id=fitcheck_id))

    if not resume_text:
        flash("Add your updated resume before you resubmit.", "error")
        return redirect(url_for("fitcheck_detail", fitcheck_id=fitcheck_id))

    result = run_fitcheck_analysis(
        pathway_profile_text=plain_text_pathway_profile(pathway_profile),
        resume_text=resume_text,
        job_description=previous_fitcheck["job_description"],
        experience_level=previous_fitcheck["experience_level"],
        job_type=previous_fitcheck["job_type"],
        previous_fitcheck=previous_fitcheck,
    )

    new_fitcheck_id = create_fitcheck(
        int(current_user()["id"]),
        parent_fitcheck_id=fitcheck_id,
        title=previous_fitcheck["title"],
        company_hint=previous_fitcheck["company_hint"],
        experience_level=previous_fitcheck["experience_level"],
        job_type=previous_fitcheck["job_type"],
        resume_text=resume_text,
        job_description=previous_fitcheck["job_description"],
        result=result,
    )
    return redirect(url_for("fitcheck_detail", fitcheck_id=new_fitcheck_id))


@app.post("/api/chat")
@pathway_profile_required
def chat():
    fitcheck_ai = get_fitcheck_ai()
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    context = payload.get("context") or {}
    pathway_profile = current_pathway_profile()
    user = current_user()

    if not question:
        return jsonify({"error": "Question is required."}), 400

    answer = fitcheck_ai.answer_chat(
        question=question,
        pathway_profile_text=plain_text_pathway_profile(pathway_profile),
        student_name=user["full_name"] if user else "Student",
        score=int(context.get("score", 0)),
        fit_band=context.get("fit_band", "Stretch"),
        experience_level=context.get("experience_level", "Junior"),
        job_type=context.get("job_type", "Other"),
        gaps=context.get("gaps", []),
        summary_lines=context.get("summary_lines", []),
        comparison=context.get("comparison"),
    )
    return jsonify({"answer": answer})


@app.context_processor
def inject_layout_context():
    return {
        "current_user": current_user(),
        "current_pathway_profile": current_pathway_profile(),
    }


if __name__ == "__main__":
    app.run(debug=True)
