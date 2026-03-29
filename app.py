from flask import Flask, render_template, request

from fitcheck.scoring import analyze_fit


app = Flask(__name__)


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


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    resume_text = SAMPLE_RESUME
    job_description = SAMPLE_JOB_DESCRIPTION
    experience_level = "Junior"
    job_type = "Software and Engineering"

    if request.method == "POST":
        resume_text = request.form.get("resume_text", "").strip()
        job_description = request.form.get("job_description", "").strip()
        experience_level = request.form.get("experience_level", experience_level)
        job_type = request.form.get("job_type", job_type)
        if resume_text and job_description:
            result = analyze_fit(
                resume_text,
                job_description,
                experience_level=experience_level,
                job_type=job_type,
            )

    return render_template(
        "index.html",
        result=result,
        resume_text=resume_text,
        job_description=job_description,
        experience_level=experience_level,
        job_type=job_type,
    )


if __name__ == "__main__":
    app.run(debug=True)
