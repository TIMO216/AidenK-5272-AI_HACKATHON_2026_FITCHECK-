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
        screener_text: str,
        job_description: str,
        experience_level: str,
        job_type: str,
        top_gaps: list[str],
    ) -> list[dict[str, str]]:
        if not self.enabled:
            return []

        prompt = (
            "You are generating the Suggestions section for FitCheck.\n"
            "Use the FitCheck voice exactly.\n"
            "Write exactly 3 suggestions.\n"
            "Each suggestion must include:\n"
            "- a short skill or gap label\n"
            "- one honest mentor-style action tied to this student's situation\n"
            "- one concrete project, networking, professor outreach, lab, or portfolio next step\n"
            "Reference the actual job description language where relevant.\n"
            "Do not use corporate language. Do not be mean. Do not be vague.\n"
            f"Student screener:\n{screener_text}\n"
            f"Experience level: {experience_level}\n"
            f"Job type: {job_type}\n"
            f"Top rule-based gaps: {json.dumps(top_gaps)}\n"
            f"Job description:\n{job_description}"
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
                        "minItems": 3,
                        "maxItems": 3,
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
        screener_text: str,
        experience_level: str,
        top_gaps: list[str],
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
            f"Student screener:\n{screener_text}\n"
            f"Final score: {final_score}\n"
            f"Fit band: {fit_band}\n"
            f"Experience level: {experience_level}\n"
            f"Top gaps: {json.dumps(top_gaps)}"
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
        score: int,
        fit_band: str,
        experience_level: str,
        job_type: str,
        gaps: list[str],
    ) -> str:
        if not self.enabled:
            return "FitCheck chat is not available yet because the OpenAI API key is not configured."

        prompt = (
            "You are answering a student inside the Ask FitCheck chat widget.\n"
            "You already know their score, fit band, experience level, and gaps.\n"
            "Maximum 3 sentences.\n"
            "If the student is just being conversational, respond like a normal human mentor and do not give advice.\n"
            "Only give advice if they clearly ask for help, analysis, feedback, what to fix, or whether they should apply.\n"
            "No corporate language. No fluff. No shaming.\n"
            f"Student score: {score}\n"
            f"Fit band: {fit_band}\n"
            f"Experience level: {experience_level}\n"
            f"Job type: {job_type}\n"
            f"Known gaps: {json.dumps(gaps)}\n"
            f"Student question: {question}"
        )

        try:
            response = self.client.responses.create(
                model=MODEL_NAME,
                instructions=FITCHECK_CHATBOT_SYSTEM_PROMPT,
                input=prompt,
                max_output_tokens=220,
            )
            return (response.output_text or "").strip() or "I do not want to fake certainty here. Ask that one more time in one sentence and I will give you the clearest next move."
        except Exception:
            return "I hit a snag talking to the AI service just now. Your score still stands, and you can try the chat again in a moment."

    def _create_structured_response(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=FITCHECK_ANALYSIS_SYSTEM_PROMPT,
            input=prompt,
            text={"format": schema},
            max_output_tokens=700,
        )
        output_text = (response.output_text or "").strip()
        if not output_text:
            return {}
        try:
            return json.loads(output_text)
        except json.JSONDecodeError:
            return {}
