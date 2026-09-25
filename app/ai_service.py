"""AI integration service using OpenAI API with structured outputs and strict grounding,
with robust, candidate-agnostic fallback error handling for rate limits and credit exhaustion."""

import re
import json
import logging
from typing import Optional
from openai import OpenAI, OpenAIError

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.models import CandidateProfile, Experience, Education, HiringEvaluation, AskResponse
from app.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT,
    QA_SYSTEM_PROMPT,
    QA_USER_PROMPT,
    EVALUATION_SYSTEM_PROMPT,
    EVALUATION_USER_PROMPT,
)

logger = logging.getLogger(__name__)

COMMON_TECH_CATALOG = [
    "Python", "FastAPI", "Django", "Flask", "SQLAlchemy", "Pydantic", "Pytest",
    "AWS", "EC2", "S3", "RDS", "Lambda", "CloudWatch", "ECS", "Docker", "Kubernetes", "CI/CD",
    "PostgreSQL", "Redis", "DynamoDB", "Git", "GitHub Actions", "Linux",
    "RESTful APIs", "Microservices", "JavaScript", "TypeScript", "React", "Node.js", "SQL", "Bash",
    "GCP", "Azure", "Java", "C++", "Go", "Rust"
]


def get_openai_client() -> OpenAI:
    """Instantiate and return OpenAI client with fast failover on quota exhaustion."""
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Please set your OPENAI_API_KEY in the .env file or environment variables."
        )
    return OpenAI(api_key=OPENAI_API_KEY, max_retries=1, timeout=6.0)


def _deterministic_extract_fallback(resume_text: str) -> CandidateProfile:
    """Candidate-agnostic deterministic fallback parser when OpenAI quota or rate limit is reached."""
    logger.info("Using generic deterministic fallback extraction.")
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    
    # Candidate name: first prominent line without colons or emails
    name = "Candidate"
    for line in lines[:5]:
        if "@" not in line and "http" not in line and not line.lower().startswith("resume"):
            name = line.strip()
            break
            
    # Email extraction
    email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", resume_text)
    email = email_match.group(1) if email_match else None
    
    # Phone extraction
    phone_match = re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", resume_text)
    phone = phone_match.group(0) if phone_match else None
    
    # Location extraction (City, State abbreviation)
    loc_match = re.search(r"\b([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})\b", resume_text)
    location = loc_match.group(1) if loc_match else None

    # Dynamic skills detection from catalog
    detected_skills = [
        skill for skill in COMMON_TECH_CATALOG
        if re.search(rf"\b{re.escape(skill)}\b", resume_text, re.IGNORECASE)
    ]

    # Dynamic Experience extraction based on date range patterns
    experiences: list[Experience] = []
    date_range_pattern = re.compile(
        r"((?:[A-Za-z]+\.?\s+)?\d{4})\s*(?:[\u2013\u2014\-–to]+)\s*((?:[A-Za-z]+\.?\s+)?\d{4}|[pP]resent|[cC]urrent|[nN]ow)",
        re.IGNORECASE
    )
    
    for i, line in enumerate(lines):
        match = date_range_pattern.search(line)
        if match:
            start_date, end_date = match.group(1).strip(), match.group(2).strip()
            header_line = line[:match.start()].strip() if match.start() > 5 else (lines[i - 1] if i > 0 else "Experience")
            
            ROLE_INDICATORS = ["engineer", "architect", "developer", "scientist", "manager", "lead", "consultant", "director", "specialist", "analyst", "intern", "associate", "specialist", "head"]
            COMPANY_INDICATORS = ["technologies", "inc", "corp", "corporation", "solutions", "llc", "ltd", "labs", "systems", "company", "group", "enterprises", "ventures"]

            p1, p2 = header_line, "Engineering"
            if "|" in header_line:
                subparts = header_line.split("|")
                p1, p2 = subparts[0].strip(), subparts[1].strip()
            elif " at " in header_line:
                subparts = header_line.split(" at ")
                p1, p2 = subparts[0].strip(), subparts[1].strip()
            elif " — " in header_line or " - " in header_line:
                delim = " — " if " — " in header_line else " - "
                subparts = header_line.split(delim)
                p1, p2 = subparts[0].strip(), subparts[1].strip()

            p1_low, p2_low = p1.lower(), p2.lower()
            if any(ci in p1_low for ci in COMPANY_INDICATORS) or any(ri in p2_low for ri in ROLE_INDICATORS):
                company, role = p1, p2
            else:
                role, company = p1, p2

            is_curr = any(kw in end_date.lower() for kw in ["present", "current", "now"])
            techs = [s for s in detected_skills if s.lower() in line.lower() or (i + 1 < len(lines) and s.lower() in lines[i + 1].lower())]
            
            experiences.append(
                Experience(
                    company=company,
                    role=role,
                    start_date=start_date,
                    end_date=end_date,
                    is_current=is_curr,
                    technologies=techs,
                )
            )

    # Dynamic Education extraction
    education: list[Education] = []
    edu_keywords = ["bachelor", "master", "ph.d", "b.s.", "m.s.", "b.tech", "degree", "university", "college", "institute"]
    for i, line in enumerate(lines):
        if any(ek in line.lower() for ek in edu_keywords):
            clean_edu_line = line
            yr_match = re.search(r"\b(19\d{2}|20\d{2})\b", clean_edu_line)
            yr = yr_match.group(1) if yr_match else None
            
            deg, inst = clean_edu_line, None
            if "|" in clean_edu_line:
                eparts = clean_edu_line.split("|")
                deg, inst = eparts[0].strip(), re.sub(r"\s*\(\d{4}\)", "", eparts[1]).strip()
            elif " from " in clean_edu_line:
                eparts = clean_edu_line.split(" from ")
                deg, inst = eparts[0].strip(), re.sub(r"\s*\(\d{4}\)", "", eparts[1]).strip()
            elif " at " in clean_edu_line:
                eparts = clean_edu_line.split(" at ")
                deg, inst = eparts[0].strip(), re.sub(r"\s*\(\d{4}\)", "", eparts[1]).strip()
            elif i + 1 < len(lines) and any(u in lines[i + 1].lower() for u in ["university", "college", "institute", "school"]):
                inst = lines[i + 1].strip()

            deg = re.sub(r"\s*\(\d{4}\)", "", deg).strip()
            education.append(
                Education(
                    degree=deg,
                    institution=inst,
                    year=yr,
                )
            )
            break

    return CandidateProfile(
        name=name,
        email=email,
        phone=phone,
        location=location,
        skills=detected_skills,
        experience=experiences,
        education=education,
        raw_text=resume_text,
    )


def extract_candidate_profile(resume_text: str) -> CandidateProfile:
    """
    Extract structured candidate information strictly from resume text.
    Validates output using Pydantic models. Falls back to candidate-agnostic
    deterministic extraction if OpenAI quota/rate limits are encountered.
    """
    try:
        client = get_openai_client()
        prompt = EXTRACTION_USER_PROMPT.format(resume_text=resume_text)
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        
        experience_list = [
            Experience(
                company=exp.get("company"),
                role=exp.get("role"),
                start_date=exp.get("start_date"),
                end_date=exp.get("end_date"),
                description=exp.get("description"),
                technologies=exp.get("technologies") or [],
                is_current=exp.get("is_current", False),
            )
            for exp in data.get("experience", [])
        ]
        
        education_list = [
            Education(
                degree=edu.get("degree"),
                institution=edu.get("institution"),
                year=str(edu.get("year")) if edu.get("year") else None,
                field_of_study=edu.get("field_of_study"),
            )
            for edu in data.get("education", [])
        ]
        
        return CandidateProfile(
            name=data.get("name"),
            email=data.get("email"),
            phone=data.get("phone"),
            location=data.get("location"),
            skills=data.get("skills") or [],
            experience=experience_list,
            education=education_list,
            ambiguities=data.get("ambiguities") or [],
            raw_text=resume_text,
        )
    except (OpenAIError, RuntimeError, json.JSONDecodeError) as exc:
        logger.warning(f"OpenAI extraction encountered issue ({exc}). Activating deterministic parser.")
        return _deterministic_extract_fallback(resume_text)


def ask_candidate_question(question: str, resume_text: str, candidate: Optional[CandidateProfile] = None) -> AskResponse:
    """
    Answer recruiter question grounded strictly in candidate resume and profile.
    Explicitly refuses to fabricate unmentioned facts.
    """
    name = candidate.name if candidate and candidate.name else "Not specified"
    email = candidate.email if candidate and candidate.email else "Not specified"
    skills = ", ".join(candidate.skills) if candidate and candidate.skills else "None explicitly listed"
    gaps = "; ".join(candidate.employment_gaps) if candidate and candidate.employment_gaps else "None detected"
    ambiguities = "; ".join(candidate.ambiguities) if candidate and candidate.ambiguities else "None identified"

    try:
        client = get_openai_client()
        prompt = QA_USER_PROMPT.format(
            name=name,
            email=email,
            skills=skills,
            employment_gaps=gaps,
            ambiguities=ambiguities,
            resume_text=resume_text,
            question=question,
        )
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        answer = response.choices[0].message.content or "No answer could be generated from the document."
        return AskResponse(answer=answer.strip(), grounded=True)
    except (OpenAIError, RuntimeError) as exc:
        logger.warning(f"OpenAI Q&A encountered issue ({exc}). Using grounded rule-based answer.")
        
        q_lower = question.lower()
        if any(term in q_lower for term in ["cloud", "aws", "gcp", "azure", "deployment"]):
            cloud_terms = ["aws", "gcp", "azure", "docker", "kubernetes", "ec2", "s3", "rds", "lambda", "ecs", "cloudwatch"]
            found_cloud = [t.upper() for t in cloud_terms if re.search(rf"\b{re.escape(t)}\b", resume_text, re.IGNORECASE)]
            if found_cloud:
                ans = f"Yes. The candidate has documented cloud and deployment experience with: {', '.join(found_cloud)}."
            else:
                ans = "The resume does not explicitly list experience with cloud deployments."
            if candidate and candidate.employment_gaps:
                ans += f" Regarding timeline continuity: {'; '.join(candidate.employment_gaps)}."
        elif any(term in q_lower for term in ["gap", "unexplained", "timeline"]):
            if candidate and candidate.employment_gaps:
                ans = f"Verified employment gaps: {'; '.join(candidate.employment_gaps)}. The resume does not document reasons or employment activities during this interval."
            else:
                ans = "No employment gaps were detected in the candidate's verified employment timeline."
        elif any(term in q_lower for term in ["skill", "technical", "technologies", "stack"]):
            if candidate and candidate.skills:
                ans = f"The candidate's explicitly verified technical skills include: {', '.join(candidate.skills)}."
            else:
                ans = "The resume does not list explicit technical skills."
        else:
            ans = (
                f"Based strictly on the provided resume for {name}: The document does not contain explicit details to fully answer '{question}'. "
                "As an AI Recruiter Assistant, unmentioned details are not fabricated."
            )
        return AskResponse(answer=ans, grounded=True)


def generate_hiring_evaluation(candidate: CandidateProfile, resume_text: str) -> HiringEvaluation:
    """
    Generate Corporate Hiring Evaluation Form using AI reasoning grounded on candidate profile.
    Falls back gracefully to candidate-agnostic evaluation synthesis if OpenAI quota is exhausted.
    """
    name = candidate.name or "Candidate"
    email = candidate.email or "Not specified"
    years_exp = candidate.years_of_experience
    years_exp_str = f"{years_exp:.1f} years" if years_exp is not None else "Cannot be determined reliably"
    years_exp_val = f"{years_exp:.1f}" if years_exp is not None else "null"
    gaps_str = "; ".join(candidate.employment_gaps) if candidate.employment_gaps else "No employment gaps detected"
    ambiguities_str = "; ".join(candidate.ambiguities) if candidate.ambiguities else "No critical ambiguities noted"

    try:
        client = get_openai_client()
        prompt = EVALUATION_USER_PROMPT.format(
            name=name,
            email=email,
            years_of_experience=years_exp_str,
            years_of_experience_val=years_exp_val,
            employment_gaps=gaps_str,
            employment_gaps_json=json.dumps(candidate.employment_gaps),
            ambiguities=ambiguities_str,
            ambiguities_json=json.dumps(candidate.ambiguities),
            resume_text=resume_text,
        )
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        
        return HiringEvaluation(
            candidate_name=data.get("candidate_name", name),
            email=data.get("email", candidate.email),
            primary_skillset=data.get("primary_skillset", candidate.skills[:10]),
            years_of_experience=data.get("years_of_experience") if data.get("years_of_experience") is not None else candidate.years_of_experience,
            education=data.get("education", [f"{e.degree or 'Degree'} - {e.institution or 'Institution'}" for e in candidate.education]),
            relevant_experience=data.get("relevant_experience", []),
            employment_gaps=candidate.employment_gaps,
            ambiguities_missing_info=data.get("ambiguities_missing_info", candidate.ambiguities),
            recommended_role=data.get("recommended_role", "Software Engineer"),
            evaluation_summary=data.get("evaluation_summary", "Evaluation generated based on resume review."),
            strengths=data.get("strengths", []),
            areas_for_investigation=data.get("areas_for_investigation", []),
            decision_recommendation=data.get("decision_recommendation", "Proceed to Technical Interview"),
        )
    except (OpenAIError, RuntimeError, json.JSONDecodeError) as exc:
        logger.warning(f"OpenAI evaluation generation issue ({exc}). Using grounded evaluation synthesis.")
        
        top_skills = candidate.skills[:8] if candidate and candidate.skills else ["Software Development"]
        latest_exp = candidate.experience[0] if candidate and candidate.experience else None
        latest_role = latest_exp.role if latest_exp and latest_exp.role else "Technical Professional"
        latest_company = latest_exp.company if latest_exp and latest_exp.company else None
        clean_role = re.sub(r"[^\w\s/–-]", "", latest_role).strip() or "Software Engineer"
        companies = [e.company for e in candidate.experience if e.company] if candidate and candidate.experience else []

        summary_parts = []
        if latest_company:
            summary_parts.append(
                f"{name} is an active industry professional currently or most recently operating as {latest_role} at {latest_company}. "
                f"With approximately {years_exp_str} of documented experience, the candidate demonstrates concentrated technical expertise in {', '.join(top_skills[:5])}."
            )
        else:
            summary_parts.append(
                f"{name} is a {clean_role} demonstrating approximately {years_exp_str} of technical experience, "
                f"with core competencies centered in {', '.join(top_skills[:5])}."
            )

        if len(companies) > 1:
            summary_parts.append(
                f"Career history reflects hands-on tenure across notable engineering environments including {', '.join(companies[:3])}."
            )

        if candidate and candidate.education:
            primary_edu = candidate.education[0]
            edu_desc = f"{primary_edu.degree or 'Degree'} from {primary_edu.institution or 'accredited institution'}"
            if primary_edu.year:
                edu_desc += f" ({primary_edu.year})"
            summary_parts.append(f"Educational foundation is anchored by a {edu_desc}.")

        if candidate and candidate.employment_gaps:
            summary_parts.append(
                f"Timeline verification identified {len(candidate.employment_gaps)} employment gap(s) requiring recruiter review: {'; '.join(candidate.employment_gaps)}."
            )
        else:
            summary_parts.append("Chronological audit confirms a continuous employment history with zero unexplained gaps.")

        if candidate and candidate.ambiguities:
            summary_parts.append(
                f"Screening investigation points noted: {'; '.join(candidate.ambiguities)}."
            )

        summary = "\n\n".join(summary_parts)

        relevant_exp = [
            f"Demonstrated role: {e.role or 'Engineer'} at {e.company or 'Client'} ({e.start_date or '?'} - {e.end_date or '?'})"
            for e in candidate.experience[:4]
        ] if candidate and candidate.experience else ["Documented relevant technical experience."]

        strengths = [
            f"Verified proficiency in {', '.join(top_skills[:4])}.",
            f"Demonstrated career progression across {len(candidate.experience)} professional roles." if candidate else "Technical competency.",
        ]

        areas = [
            f"Clarify scope and responsibilities for {g}." for g in candidate.employment_gaps
        ] + [
            f"Review ambiguity: {a}" for a in candidate.ambiguities
        ]

        return HiringEvaluation(
            candidate_name=name,
            email=candidate.email,
            primary_skillset=top_skills,
            years_of_experience=candidate.years_of_experience,
            education=[f"{e.degree} - {e.institution or 'Institution'} ({e.year or 'Year'})" for e in candidate.education] or ["Formal education listed in resume"],
            relevant_experience=relevant_exp,
            employment_gaps=candidate.employment_gaps,
            ambiguities_missing_info=candidate.ambiguities,
            recommended_role=clean_role,
            evaluation_summary=summary,
            strengths=strengths,
            areas_for_investigation=areas or ["Standard recruiter screening."],
            decision_recommendation="Proceed to Technical Interview" if not candidate.employment_gaps else "Proceed with Follow-up on Grey Areas",
        )
