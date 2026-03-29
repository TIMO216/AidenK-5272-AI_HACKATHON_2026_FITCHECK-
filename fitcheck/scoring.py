import math
import re
from collections import Counter
from typing import Optional

from fitcheck.tone import FITCHECK_SYSTEM_PROMPT, job_type_coaching_line, level_coaching_line


CATEGORY_WEIGHTS = {
    "skills_match": 35,
    "experience_relevance": 30,
    "evidence_quality": 20,
    "role_specific_signals": 15,
}

GENERIC_FILLER = {
    "hardworking",
    "fast learner",
    "team player",
    "motivated",
    "detail oriented",
    "quick learner",
}

ACTION_VERBS = {
    "built",
    "created",
    "implemented",
    "developed",
    "designed",
    "launched",
    "optimized",
    "analyzed",
    "improved",
    "reduced",
    "increased",
    "automated",
    "deployed",
    "led",
    "collaborated",
    "presented",
    "wrote",
    "tested",
}

ROLE_SIGNAL_MAP = {
    "software_engineering": {
        "trigger_terms": {
            "software engineer",
            "software engineering",
            "backend",
            "frontend",
            "full stack",
            "web application",
            "api",
            "developer",
        },
        "signal_terms": {
            "python",
            "javascript",
            "react",
            "flask",
            "sql",
            "postgresql",
            "git",
            "unit test",
            "rest api",
            "deploy",
        },
    },
    "data_analytics": {
        "trigger_terms": {
            "data analyst",
            "analytics",
            "business intelligence",
            "dashboard",
            "reporting",
            "data pipeline",
        },
        "signal_terms": {
            "sql",
            "excel",
            "tableau",
            "power bi",
            "python",
            "dashboard",
            "reporting",
            "analysis",
            "visualization",
        },
    },
    "product": {
        "trigger_terms": {
            "product manager",
            "product management",
            "roadmap",
            "stakeholder",
            "user research",
        },
        "signal_terms": {
            "stakeholder",
            "roadmap",
            "experiment",
            "user research",
            "requirements",
            "presentation",
            "cross-functional",
        },
    },
}


def analyze_fit(
    resume_text: str,
    job_description: str,
    experience_level: str = "Junior",
    job_type: str = "Software and Engineering",
) -> dict:
    resume = normalize_text(resume_text)
    job = normalize_text(job_description)

    resume_bullets = extract_bullets(resume_text)
    jd_requirements = extract_job_requirements(job_description)
    role_family = detect_role_family(job)

    category_results = {
        "skills_match": score_skills_match(resume, resume_bullets, jd_requirements),
        "experience_relevance": score_experience_relevance(resume, resume_bullets, jd_requirements),
        "evidence_quality": score_evidence_quality(resume_bullets, jd_requirements),
        "role_specific_signals": score_role_signals(resume, resume_bullets, role_family),
    }

    weighted_score = 0
    for key, value in category_results.items():
        weighted_score += value["score"] * (CATEGORY_WEIGHTS[key] / 100)

    return {
        "overall_score": round(weighted_score),
        "categories": [
            present_category("Skills Match", "skills_match", category_results["skills_match"]),
            present_category("Experience Relevance", "experience_relevance", category_results["experience_relevance"]),
            present_category("Evidence Quality", "evidence_quality", category_results["evidence_quality"]),
            present_category("Role Specific Signals", "role_specific_signals", category_results["role_specific_signals"]),
        ],
        "suggestions": build_suggestions(
            resume=resume,
            resume_bullets=resume_bullets,
            job_description=job_description,
            job_requirements=jd_requirements,
            role_family=role_family,
            category_results=category_results,
            experience_level=experience_level,
            job_type=job_type,
        ),
        "strengths": build_strengths(category_results),
        "top_requirements": [req["skill"] for req in jd_requirements[:8]],
        "top_gaps": extract_top_gaps(category_results, jd_requirements),
        "coach_summary": build_coach_summary(
            weighted_score=round(weighted_score),
            category_results=category_results,
            experience_level=experience_level,
            job_type=job_type,
        ),
        "system_prompt": FITCHECK_SYSTEM_PROMPT,
    }


def present_category(label: str, key: str, value: dict) -> dict:
    return {
        "label": label,
        "key": key,
        "weight": CATEGORY_WEIGHTS[key],
        "score": value["score"],
        "summary": value["summary"],
        "details": value["details"],
    }


def normalize_text(text: str) -> str:
    lowered = text.lower().replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9.+#/\s\\-]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def extract_bullets(text: str) -> list[str]:
    bullets = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("-", "*", "•")):
            bullets.append(stripped[1:].strip())
        elif re.match(r"^\d+\.", stripped):
            bullets.append(re.sub(r"^\d+\.\s*", "", stripped))
    if not bullets:
        chunks = [chunk.strip() for chunk in re.split(r"[.\n]", text) if len(chunk.strip()) > 35]
        bullets.extend(chunks[:12])
    return bullets


def extract_job_requirements(job_description: str) -> list[dict]:
    normalized = normalize_text(job_description)
    lines = [line.strip() for line in job_description.splitlines() if line.strip()]
    priority_counter = Counter()

    for term in extract_candidate_terms(normalized):
        priority_counter[term] += 1

    for line in lines:
        line_lower = normalize_text(line)
        weight_boost = 1
        if any(token in line_lower for token in {"required", "must", "responsibilities", "qualifications"}):
            weight_boost = 2
        if any(token in line_lower for token in {"preferred", "bonus", "nice to have"}):
            weight_boost = 0.75
        for term in extract_candidate_terms(line_lower):
            priority_counter[term] += weight_boost

    ranked = []
    for term, count in priority_counter.most_common(18):
        ranked.append(
            {
                "skill": term,
                "importance": min(1.0, 0.4 + (count / 4)),
            }
        )
    return ranked


def extract_candidate_terms(text: str) -> set[str]:
    patterns = [
        r"\bpython\b",
        r"\bflask\b",
        r"\bdjango\b",
        r"\breact\b",
        r"\bnode(?:\.js)?\b",
        r"\bjavascript\b",
        r"\btypescript\b",
        r"\bsql\b",
        r"\bpostgresql\b",
        r"\btableau\b",
        r"\bpower bi\b",
        r"\bexcel\b",
        r"\brest api(?:s)?\b",
        r"\bunit test(?:s|ing)?\b",
        r"\bdata pipeline(?:s)?\b",
        r"\bdashboard(?:s)?\b",
        r"\bstakeholder(?:s)?\b",
        r"\bproduct manager(?:s)?\b",
        r"\bcommunication\b",
        r"\bpresentation(?:s)?\b",
        r"\bdocumentation\b",
        r"\bdeployment\b",
        r"\bgit\b",
        r"\banalytics\b",
        r"\bweb app(?:lication)?s?\b",
    ]
    found = set()
    for pattern in patterns:
        for match in re.findall(pattern, text):
            found.add(singularize(match))
    return found


def singularize(term: str) -> str:
    replacements = {
        "rest apis": "rest api",
        "unit tests": "unit test",
        "unit testing": "unit test",
        "dashboards": "dashboard",
        "data pipelines": "data pipeline",
        "product managers": "product manager",
        "stakeholders": "stakeholder",
        "presentations": "presentation",
    }
    term = re.sub(r"\s+", " ", term.lower()).strip()
    return replacements.get(term, term)


def score_skills_match(resume: str, resume_bullets: list[str], requirements: list[dict]) -> dict:
    if not requirements:
        return empty_category("No concrete skill requirements were detected in the job description.", 55)

    evidence_hits = []
    total_importance = sum(req["importance"] for req in requirements)
    weighted_match = 0.0

    for req in requirements:
        evidence = find_skill_evidence(req["skill"], resume, resume_bullets)
        weighted_match += req["importance"] * evidence["strength"]
        evidence_hits.append(
            {
                "skill": req["skill"].title(),
                "strength": round(evidence["strength"] * 100),
                "evidence": evidence["snippet"],
            }
        )

    score = safe_round(100 * (weighted_match / total_importance))
    strong = sum(1 for item in evidence_hits if item["strength"] >= 70)
    return {
        "score": max(18, min(score, 96)),
        "summary": f"You matched {strong} of {len(evidence_hits)} important requirements with proof on the page, not just keywords.",
        "details": evidence_hits[:6],
    }


def score_experience_relevance(resume: str, resume_bullets: list[str], requirements: list[dict]) -> dict:
    if not resume_bullets:
        return empty_category("No clear experience examples were found, so relevance cannot be supported yet.", 20)

    role_terms = {req["skill"] for req in requirements}
    relevant_bullets = []
    for bullet in resume_bullets:
        bullet_norm = normalize_text(bullet)
        overlap = sum(1 for term in role_terms if term in bullet_norm)
        if overlap:
            relevant_bullets.append((bullet, overlap))

    top_overlap = max((overlap for _, overlap in relevant_bullets), default=0)
    relevant_ratio = len(relevant_bullets) / max(1, len(resume_bullets))
    quality_bonus = 0.0
    if relevant_bullets:
        quality_bonus = sum(evidence_quality_factor(bullet) for bullet, _ in relevant_bullets) / len(relevant_bullets)

    years = infer_years_of_experience(resume)
    years_factor = min(years / 3, 1.0) if years else 0.2
    score = (
        relevant_ratio * 45
        + min(top_overlap / 3, 1.0) * 25
        + quality_bonus * 20
        + years_factor * 10
    )

    return {
        "score": max(12, min(safe_round(score), 92)),
        "summary": (
            f"{len(relevant_bullets)} of {len(resume_bullets)} experience examples actually line up with this role, "
            f"and the best examples hit {top_overlap} direct requirement signals."
        ),
        "details": [
            {
                "skill": f"Relevant example {index + 1}",
                "strength": min(100, 35 + overlap * 18 + safe_round(evidence_quality_factor(bullet) * 25)),
                "evidence": trim_snippet(bullet),
            }
            for index, (bullet, overlap) in enumerate(sorted(relevant_bullets, key=lambda item: item[1], reverse=True)[:4])
        ],
    }


def score_evidence_quality(resume_bullets: list[str], requirements: list[dict]) -> dict:
    if not resume_bullets:
        return empty_category("No clear achievement examples were found to evaluate evidence quality.", 15)

    bullet_scores = []
    req_terms = {req["skill"] for req in requirements}
    for bullet in resume_bullets:
        factor = evidence_quality_factor(bullet)
        role_overlap = sum(1 for term in req_terms if term in normalize_text(bullet))
        bullet_scores.append((bullet, factor, role_overlap))

    average_factor = sum(score for _, score, _ in bullet_scores) / len(bullet_scores)
    targeted_factor = sum(min(1.0, overlap / 2) for _, _, overlap in bullet_scores) / len(bullet_scores)
    score = max(20, min(safe_round((average_factor * 70) + (targeted_factor * 30)), 95))

    return {
        "score": score,
        "summary": "This score checks whether your examples prove what you did, who it helped, and what changed because of your work.",
        "details": [
            {
                "skill": "High-quality evidence" if factor >= 0.65 else "Weak evidence",
                "strength": safe_round(factor * 100),
                "evidence": trim_snippet(bullet),
            }
            for bullet, factor, _ in sorted(bullet_scores, key=lambda item: item[1], reverse=True)[:4]
        ],
    }


def score_role_signals(resume: str, resume_bullets: list[str], role_family: Optional[str]) -> dict:
    if not role_family:
        fallback = min(70, 25 + safe_round(sum(evidence_quality_factor(b) for b in resume_bullets[:3]) * 10))
        return empty_category("Used general student-role signals because the target role family was broad.", fallback)

    config = ROLE_SIGNAL_MAP[role_family]
    explicit_signals = []
    for term in config["signal_terms"]:
        evidence = find_skill_evidence(term, resume, resume_bullets)
        if evidence["strength"] > 0:
            explicit_signals.append((term, evidence))

    internship_bonus = 0.15 if "intern" in resume else 0.0
    project_bonus = 0.1 if "project" in resume else 0.0
    education_bonus = 0.08 if "university" in resume or "student" in resume else 0.0
    signal_density = len(explicit_signals) / max(4, len(config["signal_terms"]) / 2)
    evidence_strength = (
        sum(item["strength"] for _, item in explicit_signals) / len(explicit_signals)
        if explicit_signals
        else 0.0
    )
    raw_score = (signal_density * 55) + (evidence_strength * 30) + ((internship_bonus + project_bonus + education_bonus) * 100)

    return {
        "score": max(10, min(safe_round(raw_score), 90)),
        "summary": f"We found {len(explicit_signals)} explicit {role_family.replace('_', ' ')} signals that a recruiter would actually recognize.",
        "details": [
            {
                "skill": term.title(),
                "strength": safe_round(evidence["strength"] * 100),
                "evidence": evidence["snippet"],
            }
            for term, evidence in explicit_signals[:5]
        ],
    }


def find_skill_evidence(skill: str, resume: str, bullets: list[str]) -> dict:
    normalized_skill = normalize_text(skill)
    exact_match = normalized_skill in resume
    matching_bullets = [bullet for bullet in bullets if normalized_skill in normalize_text(bullet)]
    if matching_bullets:
        bullet = best_bullet_for_skill(normalized_skill, matching_bullets)
        return {
            "strength": min(1.0, 0.55 + evidence_quality_factor(bullet)),
            "snippet": trim_snippet(bullet),
        }
    if exact_match:
        return {
            "strength": 0.45,
            "snippet": "Mentioned, but not backed by a concrete example.",
        }
    return {
        "strength": 0.0,
        "snippet": "No direct evidence found.",
    }


def best_bullet_for_skill(skill: str, bullets: list[str]) -> str:
    scored = []
    for bullet in bullets:
        quality = evidence_quality_factor(bullet)
        overlap = len(set(skill.split()) & set(normalize_text(bullet).split()))
        scored.append((quality + (overlap * 0.05), bullet))
    scored.sort(reverse=True)
    return scored[0][1]


def infer_years_of_experience(resume: str) -> float:
    matches = re.findall(r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)", resume)
    values = [float(match) for match in matches]
    return max(values) if values else 0.0


def evidence_quality_factor(bullet: str) -> float:
    normalized = normalize_text(bullet)
    words = normalized.split()
    has_metric = bool(re.search(r"\b\d+[%+x]?\b|\b\d+\s+(?:hours|users|students|projects|weeks|months)\b", normalized))
    has_action = any(word in ACTION_VERBS for word in words[:4]) or any(f" {verb} " in f" {normalized} " for verb in ACTION_VERBS)
    has_outcome = any(token in normalized for token in {"improved", "reduced", "increased", "cut", "grew", "launched", "used by"})
    has_context = len(words) >= 10
    generic_penalty = any(phrase in normalized for phrase in GENERIC_FILLER)

    score = 0.15
    if has_action:
        score += 0.25
    if has_context:
        score += 0.15
    if has_metric:
        score += 0.25
    if has_outcome:
        score += 0.15
    if re.search(r"\bwith\b|\bfor\b|\busing\b", normalized):
        score += 0.1
    if generic_penalty:
        score -= 0.2
    return max(0.05, min(score, 1.0))


def detect_role_family(job_description: str) -> Optional[str]:
    for role_family, config in ROLE_SIGNAL_MAP.items():
        if any(term in job_description for term in config["trigger_terms"]):
            return role_family
    return None


def build_suggestions(
    resume: str,
    resume_bullets: list[str],
    job_description: str,
    job_requirements: list[dict],
    role_family: Optional[str],
    category_results: dict,
    experience_level: str,
    job_type: str,
) -> list[dict]:
    suggestions = []
    jd_sentences = [line.strip(" -") for line in job_description.splitlines() if len(line.strip()) > 20]

    sorted_requirements = sorted(job_requirements, key=lambda req: req["importance"], reverse=True)
    for req in sorted_requirements:
        evidence = find_skill_evidence(req["skill"], resume, resume_bullets)
        if evidence["strength"] >= 0.55:
            continue
        jd_context = next((sentence for sentence in jd_sentences if req["skill"] in normalize_text(sentence)), "")
        suggestions.append(
            {
                "title": f"Strengthen evidence for {req['skill'].title()}",
                "body": build_skill_specific_suggestion(req["skill"], jd_context, role_family, evidence["strength"]),
                "priority": "High" if req["importance"] >= 0.8 else "Medium",
            }
        )
        if len(suggestions) == 4:
            break

    if category_results["experience_relevance"]["score"] < 60:
        suggestions.append(
            {
                "title": "Build more role-relevant proof",
                "body": "The experience is still a little too far from what this role actually does. The next move is to get one hands-on example that clearly overlaps with the job.",
                "priority": "High",
            }
        )

    if category_results["evidence_quality"]["score"] < 65:
        suggestions.append(
            {
                "title": "Build stronger proof",
                "body": "Right now the proof is still thinner than it needs to be. Focus on one project, class result, lab outcome, or real-world example that shows what changed because of your work.",
                "priority": "Medium",
            }
        )

    return suggestions[:5]


def build_skill_specific_suggestion(skill: str, jd_context: str, role_family: Optional[str], evidence_strength: float) -> str:
    if evidence_strength == 0:
        prefix = f"The job description explicitly asks for {skill}, and right now your resume does not prove it."
    else:
        prefix = f"You mention {skill}, but the proof is still thin."

    action_map = {
        "python": "Build or finish one Python example you can talk through clearly, like a script, automation, or small app.",
        "flask": "Create one small Flask app or internal tool so you have real experience using it, not just familiarity.",
        "sql": "Practice SQL in a real setting, like a project, dataset, or reporting task where you can explain the question and result.",
        "postgresql": "Use PostgreSQL in a small project where you can talk about the data model and why it was set up that way.",
        "rest api": "Build or connect to one API so you can explain what data moved and why it mattered.",
        "unit test": "Write tests for one project you already have so you can talk about how you checked reliability.",
        "dashboard": "Create one dashboard tied to a real question so you can explain the decision it supports.",
        "data pipeline": "Build one small end-to-end data flow so you can explain where data came from and what changed at the end.",
        "stakeholder": "Get one experience where you had to align with another person or team and explain what decision came out of it.",
        "presentation": "Practice presenting one project or analysis clearly to another person, class, or mentor.",
        "documentation": "Write one clear setup guide, walkthrough, or project explanation for something you built.",
    }
    action = action_map.get(
        skill,
        f"Get one concrete example of {skill} in a project, internship, class, campus role, or research setting so you can talk about it with confidence.",
    )
    context = f" In this role, it shows up in: \"{trim_snippet(jd_context)}\"." if jd_context else ""
    role_nudge = ""
    if role_family == "software_engineering":
        role_nudge = " Focus on shipped features, APIs, testing, or deployment evidence."
    elif role_family == "data_analytics":
        role_nudge = " Focus on analyses, dashboards, data cleaning, or reporting outcomes."
    elif role_family == "product":
        role_nudge = " Focus on user insight, stakeholder alignment, and decisions influenced."
    return prefix + context + " " + action + role_nudge


def build_coach_summary(weighted_score: int, category_results: dict, experience_level: str, job_type: str) -> list[str]:
    weakest_category = min(category_results.items(), key=lambda item: item[1]["score"])[0]
    weakest_labels = {
        "skills_match": "skill proof",
        "experience_relevance": "role relevance",
        "evidence_quality": "evidence quality",
        "role_specific_signals": "role-specific credibility",
    }

    if weighted_score >= 80:
        line_one = "You are in a good spot for this role. The resume already shows real proof, not just interest."
    elif weighted_score >= 60:
        line_one = "You have a real shot here, but a recruiter would still see a few places where the proof is lighter than it needs to be."
    else:
        line_one = "This role is a stretch right now, and FitCheck should say that plainly. The gap is not interest. The gap is proof."

    line_two = level_coaching_line(experience_level)
    line_three = f"Your biggest weakness right now is {weakest_labels[weakest_category]}. {job_type_coaching_line(job_type)}"
    return [line_one, line_two, line_three]


def extract_top_gaps(category_results: dict, job_requirements: list[dict]) -> list[str]:
    gaps = []

    weak_skill_details = [
        detail["skill"]
        for detail in category_results["skills_match"]["details"]
        if detail["strength"] < 55
    ]
    gaps.extend(weak_skill_details[:3])

    if category_results["experience_relevance"]["score"] < 60:
        gaps.append("role-relevant experience is not obvious enough on the page")
    if category_results["evidence_quality"]["score"] < 65:
        gaps.append("the current examples do not prove impact strongly enough")
    if category_results["role_specific_signals"]["score"] < 60:
        gaps.append("role-specific signals are too thin for this type of job")

    for requirement in job_requirements[:5]:
        titled = requirement["skill"].title()
        if titled not in gaps:
            gaps.append(titled)

    deduped = []
    seen = set()
    for gap in gaps:
        normalized = gap.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(gap)
    return deduped[:3]


def build_strengths(category_results: dict) -> list[str]:
    strengths = []
    strong_skills = [
        item["skill"]
        for item in category_results["skills_match"]["details"]
        if item["strength"] >= 70
    ]
    if strong_skills:
        strengths.append("Strong evidence for " + ", ".join(strong_skills[:3]) + ".")
    strongest_experience = category_results["experience_relevance"]["details"][:1]
    if strongest_experience:
        strengths.append("Most relevant experience example: " + strongest_experience[0]["evidence"])
    if category_results["evidence_quality"]["score"] >= 70:
        strengths.append("Your strongest examples generally include action and outcomes instead of only tool names.")
    if not strengths:
        strengths.append("Resume shows some overlap with the role, but needs stronger proof in the highest-priority areas.")
    return strengths[:3]


def trim_snippet(text: str, limit: int = 135) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def safe_round(value: float) -> int:
    return int(math.floor(value + 0.5))


def empty_category(summary: str, score: int) -> dict:
    return {"score": score, "summary": summary, "details": []}
