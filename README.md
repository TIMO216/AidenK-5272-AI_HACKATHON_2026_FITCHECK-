# FitCheck

FitCheck is a Flask MVP that scores how well a student resume fits a job description.

## What it does

- Accepts a pasted resume and job description
- Scores fit across four weighted categories:
  - Skills Match: 35%
  - Experience Relevance: 30%
  - Evidence Quality: 20%
  - Role Specific Signals: 15%
- Produces targeted suggestions based on missing or weak evidence for the actual job requirements

## Run locally

1. Create a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Start the app with `flask --app app run --debug`.
4. Open the local Flask URL in your browser.

## Notes

- The scoring is rule-based and intentionally avoids awarding perfect category scores unless the resume shows repeated, specific, high-quality evidence.
- Suggestions are generated from the job description’s top requirements and the exact evidence gaps detected in the resume.
