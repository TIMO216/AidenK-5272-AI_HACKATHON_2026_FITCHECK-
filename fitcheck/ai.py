import json
import os
from typing import Any

from openai import OpenAI

from fitcheck.tone import (
    FITCHECK_ANALYSIS_SYSTEM_PROMPT,
    FITCHECK_CHATBOT_SYSTEM_PROMPT,
    FITCHECK_SYSTEM_PROMPT,
)


MODEL_NAME = "gpt-4o"


class FitCheckAI:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def generate_suggestions(
        self,
        *,
        pathway_profile_text: str,
        job_description: str,
        experience_level: str,
        job_type: str,
        top_gaps: list[str],
        resubmit_context: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        if not self.enabled:
            return []

        target_count = 3 if not resubmit_context else max(1, min(2, len(top_gaps) or 1))
        prompt = (
            "You are generating the Suggestions section for FitCheck.\n"
            "Use the FitCheck voice exactly.\n"
            f"Write exactly {target_count} suggestions.\n"
            "Each suggestion must include:\n"
            "- a short skill or gap label\n"
            "- one honest mentor-style explanation of what would actually move this student forward\n"
            "- one grounded example of what makes sense next, such as a project idea, professor outreach move, campus resource, credential, or portfolio direction\n"
            "Reference the actual job description language where relevant.\n"
            "Do not use corporate language. Do not be mean. Do not be vague.\n"
            "Do not give editing advice, writing critique, or formatting suggestions.\n"
            "Do not sound like a checklist, task list, or productivity app.\n"
            f"Student Pathway Profile:\n{pathway_profile_text}\n"
            f"Experience level: {experience_level}\n"
            f"Job type: {job_type}\n"
            f"Top rule-based gaps: {json.dumps(top_gaps)}\n"
            f"Job description:\n{job_description}"
        )
        if resubmit_context:
            prompt += (
                "\nThis is a resubmission.\n"
                f"What changed: {json.dumps(resubmit_context.get('what_changed', []))}\n"
                f"What improved: {json.dumps(resubmit_context.get('what_improved', []))}\n"
                f"What's left: {json.dumps(resubmit_context.get('whats_left', []))}\n"
                "Acknowledge progress.\n"
                "Do not repeat old advice that was already addressed.\n"
                "Do not invent new flaws.\n"
                "Focus only on the 1 to 2 remaining meaningful gaps.\n"
                "Do not turn this into critique about wording, structure, or presentation.\n"
            )

        schema = {
            "type": "json_schema",
            "name": "fitcheck_suggestions",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "suggestions": {
                        "type": "array",
                        "minItems": target_count,
                        "maxItems": target_count,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "title": {"type": "string"},
                                "body": {"type": "string"},
                                "resource": {"type": "string"},
                            },
                            "required": ["title", "body", "resource"],
                        },
                    }
                },
                "required": ["suggestions"],
            },
        }

        try:
            payload = self._create_structured_response(prompt, schema)
            suggestions = payload.get("suggestions", [])
            return suggestions if isinstance(suggestions, list) else []
        except Exception:
            return []

    def generate_summary(
        self,
        *,
        final_score: int,
        fit_band: str,
        pathway_profile_text: str,
        experience_level: str,
        top_gaps: list[str],
        resubmit_context: dict[str, Any] | None = None,
    ) -> list[str]:
        if not self.enabled:
            return []

        prompt = (
            "You are generating the honest summary at the top of the FitCheck results screen.\n"
            "Write 2 to 3 short sentences in the FitCheck voice.\n"
            "Be plain, specific, direct, and respectful.\n"
            "Mention whether this student is strong, moderate, or a stretch for this role.\n"
            "Use their timing and experience level realistically.\n"
            "No corporate language.\n"
            f"Student Pathway Profile:\n{pathway_profile_text}\n"
            f"Final score: {final_score}\n"
            f"Fit band: {fit_band}\n"
            f"Experience level: {experience_level}\n"
            f"Top gaps: {json.dumps(top_gaps)}"
        )
        if resubmit_context:
            prompt += (
                "\nThis is a resubmission.\n"
                f"Previous score: {resubmit_context.get('previous_score', 0)}\n"
                f"What changed: {json.dumps(resubmit_context.get('what_changed', []))}\n"
                f"What improved: {json.dumps(resubmit_context.get('what_improved', []))}\n"
                f"What's left: {json.dumps(resubmit_context.get('whats_left', []))}\n"
                "Acknowledge improvements clearly.\n"
                "Do not repeat old advice.\n"
                "Do not invent new flaws.\n"
                "If the student is now competitive, say so and stop criticizing.\n"
                "Do not shift into critique about wording, formatting, or presentation.\n"
            )

        schema = {
            "type": "json_schema",
            "name": "fitcheck_summary",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary_lines": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 3,
                        "items": {"type": "string"},
                    }
                },
                "required": ["summary_lines"],
            },
        }

        try:
            payload = self._create_structured_response(prompt, schema)
            lines = payload.get("summary_lines", [])
            return lines if isinstance(lines, list) else []
        except Exception:
            return []

    def answer_chat(
        self,
        *,
        question: str,
        pathway_profile_text: str,
        student_name: str,
        score: int,
        fit_band: str,
        experience_level: str,
        job_type: str,
        gaps: list[str],
        summary_lines: list[str],
        comparison: dict[str, Any] | None = None,
    ) -> str:
        if not self.enabled:
            return "FitCheck chat is not available yet because the OpenAI API key is not configured."

        prompt = (
            "You are answering a student inside the Ask FitCheck chat widget.\n"
            "You already know their Pathway Profile, score, fit band, experience level, and gaps.\n"
            "Maximum 3 sentences.\n"
            "If the student is just being conversational, respond like a normal human mentor and do not give advice.\n"
            "Only give advice if they clearly ask for help, analysis, feedback, what to fix, or whether they should apply.\n"
            "No corporate language. No fluff. No shaming.\n"
            "Do not act like an editor, grader, or writing coach.\n"
            "Do not sound like a task list or productivity app.\n"
            "Offer direction, not assignments.\n"
            f"Student name: {student_name}\n"
            f"Student Pathway Profile:\n{pathway_profile_text}\n"
            f"Student score: {score}\n"
            f"Fit band: {fit_band}\n"
            f"Experience level: {experience_level}\n"
            f"Job type: {job_type}\n"
            f"Known gaps: {json.dumps(gaps)}\n"
            f"FitCheck summary: {json.dumps(summary_lines)}\n"
            f"Student question: {question}"
        )
        if comparison:
            prompt += (
                "\nThis student resubmitted.\n"
                f"What changed: {json.dumps(comparison.get('what_changed', []))}\n"
                f"What improved: {json.dumps(comparison.get('what_improved', []))}\n"
                f"What's left: {json.dumps(comparison.get('whats_left', []))}\n"
                "Encourage healthy progress.\n"
                "Avoid perfectionism, overwork, or endless editing.\n"
                "Do not shift into critique about wording, structure, formatting, or presentation.\n"
            )

        try:
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": FITCHECK_CHATBOT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=220,
            )
            return (response.choices[0].message.content or "").strip() or "I do not want to fake certainty here. Ask that one more time in one sentence and I will give you the clearest next move."
        except Exception as e:
            print(f"Chat error: {e}")
            return "I hit a snag talking to the AI service just now. Your score still stands, and you can try the chat again in a moment."

    def _create_structured_response(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": FITCHECK_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_schema", "json_schema": schema},
            max_tokens=700,
        )
        output_text = (response.choices[0].message.content or "").strip()
        if not output_text:
            return {}
        try:
            return json.loads(output_text)
        except json.JSONDecodeError:
            return {}
