import re
from typing import Any


COMMON_GAP_WORDS = {
    "and",
    "the",
    "for",
    "this",
    "that",
    "with",
    "your",
    "role",
    "type",
    "job",
    "specific",
    "too",
    "not",
    "enough",
    "strongly",
    "proof",
    "page",
    "obvious",
    "experience",
    "signals",
}


def build_resubmit_comparison(previous_fitcheck: dict[str, Any], new_result: dict[str, Any], new_resume_text: str) -> dict[str, Any]:
    previous_result = previous_fitcheck["result"]
    old_resume_text = previous_fitcheck["resume_text"]

    previous_categories = {
        category["key"]: category["score"]
        for category in previous_result.get("categories", [])
    }
    current_categories = {
        category["key"]: category["score"]
        for category in new_result.get("categories", [])
    }

    changed = extract_changed_lines(old_resume_text, new_resume_text)
    remaining = [] if new_result["overall_score"] >= 80 else find_remaining_gaps(
        previous_result.get("top_gaps", []),
        new_result.get("top_gaps", []),
    )
    improved = build_improvement_list(
        previous_result=previous_result,
        new_result=new_result,
        previous_categories=previous_categories,
        current_categories=current_categories,
        remaining=remaining,
    )

    return {
        "is_resubmission": True,
        "previous_fitcheck_id": previous_fitcheck["id"],
        "previous_score": previous_result.get("overall_score", 0),
        "current_score": new_result.get("overall_score", 0),
        "score_change": new_result.get("overall_score", 0) - previous_result.get("overall_score", 0),
        "what_changed": changed[:3],
        "what_improved": improved[:3],
        "whats_left": remaining[:2],
    }


def extract_changed_lines(old_text: str, new_text: str) -> list[str]:
    old_lines = normalized_lines(old_text)
    new_lines = normalized_lines(new_text)
    old_lookup = {normalize_line(line) for line in old_lines}

    additions = [line for line in new_lines if normalize_line(line) not in old_lookup]
    if additions:
        return additions[:3]

    if old_text.strip() != new_text.strip():
        return ["You made meaningful updates to your experience and supporting details."]

    return ["No major changes were detected between the last version and this one."]


def build_improvement_list(
    *,
    previous_result: dict[str, Any],
    new_result: dict[str, Any],
    previous_categories: dict[str, int],
    current_categories: dict[str, int],
    remaining: list[str],
) -> list[str]:
    improvements: list[str] = []

    previous_gaps = previous_result.get("top_gaps", [])
    for gap in previous_gaps:
        if gap not in remaining:
            improvements.append(f"You addressed {gap.lower()}.")

    labels = {
        "skills_match": "skill proof",
        "experience_relevance": "role relevance",
        "evidence_quality": "evidence strength",
        "role_specific_signals": "role-specific credibility",
    }
    for key, old_score in previous_categories.items():
        new_score = current_categories.get(key, old_score)
        if new_score - old_score >= 6:
            improvements.append(f"Your {labels.get(key, key)} improved from {old_score} to {new_score}.")

    if not improvements and new_result.get("overall_score", 0) > previous_result.get("overall_score", 0):
        improvements.append("This version is clearly stronger overall than the last one.")

    if not improvements:
        improvements.append("This version is steadier, but the biggest priorities are still mostly the same.")

    return dedupe_preserve_order(improvements)


def find_remaining_gaps(previous_gaps: list[str], new_gaps: list[str]) -> list[str]:
    remaining: list[str] = []
    for previous_gap in previous_gaps:
        if any(gap_matches(previous_gap, current_gap) for current_gap in new_gaps):
            remaining.append(previous_gap)
    return dedupe_preserve_order(remaining)[:2]


def gap_matches(previous_gap: str, current_gap: str) -> bool:
    if normalize_line(previous_gap) == normalize_line(current_gap):
        return True

    previous_tokens = meaningful_tokens(previous_gap)
    current_tokens = meaningful_tokens(current_gap)
    return bool(previous_tokens and current_tokens and previous_tokens.intersection(current_tokens))


def normalized_lines(text: str) -> list[str]:
    seen = set()
    cleaned: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 18:
            continue
        normalized = normalize_line(line)
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(line)
    return cleaned


def normalize_line(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def meaningful_tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_line(text).split()
        if len(token) > 2 and token not in COMMON_GAP_WORDS
    }


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for item in items:
        key = normalize_line(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
