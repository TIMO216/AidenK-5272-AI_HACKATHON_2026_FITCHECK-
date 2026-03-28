import math
import re
from collections import Counter
from typing import Optional


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


def analyze_fit(resume_text: str, job_description: str) -> dict:
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
        ),
        "strengths": build_strengths(category_results),
        "top_requirements": [req["skill"] for req in jd_requirements[:8]],
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
    lowered = re.sub(r"[^a-z0-9.+#/\\-\s]", " ", lowered)
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
        "summary": f"Matched {strong} of {len(evidence_hits)} high-value requirements with concrete evidence.",
        "details": evidence_hits[:6],
    }


def score_experience_relevance(resume: str, resume_bullets: list[str], requirements: list[dict]) -> dict:
    if not resume_bullets:
        return empty_category("No experience bullets were found, so relevance cannot be supported.", 20)

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
            f"{len(relevant_bullets)} of {len(resume_bullets)} bullets align with the role, "
            f"with the strongest examples showing {top_overlap} direct requirement overlaps."
        ),
        "details": [
            {
                "skill": f"Relevant bullet {index + 1}",
                "strength": min(100, 35 + overlap * 18 + safe_round(evidence_quality_factor(bullet) * 25)),
                "evidence": trim_snippet(bullet),
            }
            for index, (bullet, overlap) in enumerate(sorted(relevant_bullets, key=lambda item: item[1], reverse=True)[:4])
        ],
    }


def score_evidence_quality(resume_bullets: list[str], requirements: list[dict]) -> dict:
    if not resume_bullets:
        return empty_category("No achievement bullets were found to evaluate evidence quality.", 15)

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
        "summary": "Evidence quality reflects whether bullets show action, scope, and outcomes for the role needs.",
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
        "summary": f"Detected {len(explicit_signals)} explicit {role_family.replace('_', ' ')} signals in the resume.",
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
            "snippet": "Mentioned in resume, but not backed by a concrete bullet.",
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
                "title": "Make role-relevant work easier to spot",
                "body": "Move the bullets that best match this job closer to the top of each experience entry and rewrite them to mirror the job’s tasks, not just the tool list.",
                "priority": "High",
            }
        )

    if category_results["evidence_quality"]["score"] < 65:
        suggestions.append(
            {
                "title": "Add outcomes to weak bullets",
                "body": "Several bullets mention tools without proving impact. Add scope, speed, accuracy, adoption, or time-saved metrics so each line shows what changed because of your work.",
                "priority": "Medium",
            }
        )

    return suggestions[:5]


def build_skill_specific_suggestion(skill: str, jd_context: str, role_family: Optional[str], evidence_strength: float) -> str:
    if evidence_strength == 0:
        prefix = f"The job description explicitly asks for {skill}, but your resume does not show it yet."
    else:
        prefix = f"{skill.title()} appears on the resume, but the evidence is still light."

    action_map = {
        "python": "Name the script, service, or automation you built in Python and what it delivered.",
        "flask": "Call out the route, API, or internal tool you built with Flask instead of listing Flask only in the skills section.",
        "sql": "Add a bullet describing the query, reporting workflow, or database task you handled with SQL.",
        "postgresql": "Mention the schema, dashboard, or data model work you did in PostgreSQL.",
        "rest api": "Describe the endpoint or integration you implemented and who used it.",
        "unit test": "State what you tested, which bugs it prevented, or how coverage improved.",
        "dashboard": "Show the audience, metric, and decision supported by the dashboard.",
        "data pipeline": "Explain the source-to-output flow and the reliability or time savings it created.",
        "stakeholder": "Mention the stakeholders you worked with and what decision or demo came out of that collaboration.",
        "presentation": "Include what you presented, to whom, and why it mattered.",
        "documentation": "Add the technical docs, runbooks, or design notes you wrote and how they were used.",
    }
    action = action_map.get(
        skill,
        f"Add a bullet that shows where you used {skill} in a project, internship, class, or campus role and what measurable result it produced.",
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
        strengths.append("Most relevant experience bullet: " + strongest_experience[0]["evidence"])
    if category_results["evidence_quality"]["score"] >= 70:
        strengths.append("Achievement bullets generally include action and outcomes instead of only tool names.")
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
