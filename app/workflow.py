"""Agentic workflow orchestration for candidate extraction, deterministic analysis, and evaluation."""

import re
import logging
from datetime import date
from typing import Optional

from app.models import (
    CandidateProfile,
    Experience,
    HiringEvaluation,
    WorkflowResult,
    WorkflowStep,
)
from app.ai_service import extract_candidate_profile, generate_hiring_evaluation
from app.document_service import generate_evaluation_pdf

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def parse_date_string(date_str: Optional[str]) -> Optional[date]:
    """
    Deterministically parse month/year date strings into a date object.
    Supports formats like:
      - 'June 2020', 'Jun 2020', '06/2020', '2020-06', '2020'
      - 'Present', 'Current', 'Now' -> today's date
    """
    if not date_str:
        return None
        
    s = date_str.strip().lower()
    
    if any(keyword in s for keyword in ["present", "current", "now", "ongoing"]):
        return date.today()
        
    # Match Month Year (e.g., 'June 2020', 'Jan 2021')
    month_year_match = re.search(r"([a-z]+)\.?\s+(\d{4})", s)
    if month_year_match:
        m_str, y_str = month_year_match.groups()
        month = MONTH_MAP.get(m_str)
        if month:
            return date(int(y_str), month, 1)

    # Match MM/YYYY or MM-YYYY
    slash_match = re.search(r"(\d{1,2})[\/\-](\d{4})", s)
    if slash_match:
        m_str, y_str = slash_match.groups()
        month = int(m_str)
        if 1 <= month <= 12:
            return date(int(y_str), month, 1)

    # Match YYYY-MM
    iso_match = re.search(r"(\d{4})[\/\-](\d{1,2})", s)
    if iso_match:
        y_str, m_str = iso_match.groups()
        month = int(m_str)
        if 1 <= month <= 12:
            return date(int(y_str), month, 1)

    # Match Year only (e.g., '2020')
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", s)
    if year_match:
        return date(int(year_match.group(1)), 1, 1)

    return None


def calculate_employment_history_and_gaps(candidate: CandidateProfile) -> CandidateProfile:
    """
    Deterministic calculation of employment gaps and total years of experience.
    Strictly avoids LLM hallucinations for date arithmetic.
    """
    parsed_entries: list[tuple[date, date, Experience]] = []
    has_unparseable_dates = False
    
    for exp in candidate.experience:
        start_dt = parse_date_string(exp.start_date)
        end_dt = parse_date_string(exp.end_date)
        
        if exp.is_current and not end_dt:
            end_dt = date.today()
            
        if start_dt and end_dt:
            # If end is before start due to year inversion or single-year edge case, normalize
            if end_dt < start_dt:
                start_dt, end_dt = end_dt, start_dt
            parsed_entries.append((start_dt, end_dt, exp))
        else:
            if exp.start_date or exp.end_date:
                has_unparseable_dates = True

    # If any role had unparseable dates or no valid dates at all
    gaps: list[str] = []
    if has_unparseable_dates:
        candidate.ambiguities.append(
            "Employment gap cannot be reliably determined because the resume does not provide complete dates."
        )

    if not parsed_entries:
        if not candidate.years_of_experience:
            candidate.years_of_experience = None
        candidate.employment_gaps = gaps
        return candidate

    # Sort experiences chronologically by start date
    parsed_entries.sort(key=lambda item: item[0])

    # Calculate gaps between consecutive employment intervals
    max_end_so_far = parsed_entries[0][1]
    last_active_exp = parsed_entries[0][2]

    for i in range(1, len(parsed_entries)):
        next_start, next_end, next_exp = parsed_entries[i]

        # Check gap between the latest date the candidate was actively employed and the next start
        if next_start > max_end_so_far:
            month_diff = (next_start.year - max_end_so_far.year) * 12 + (next_start.month - max_end_so_far.month)
            if month_diff >= 2:
                gap_desc = (
                    f"Detected ~{month_diff}-month gap between {last_active_exp.end_date or max_end_so_far.strftime('%b %Y')} "
                    f"({last_active_exp.company or 'Previous Role'}) and {next_exp.start_date or next_start.strftime('%b %Y')} "
                    f"({next_exp.company or 'Next Role'})"
                )
                gaps.append(gap_desc)

        if next_end > max_end_so_far:
            max_end_so_far = next_end
            last_active_exp = next_exp

    candidate.employment_gaps = gaps

    # Calculate total non-overlapping months of experience
    # Merge overlapping intervals
    merged_intervals: list[tuple[date, date]] = []
    for s_dt, e_dt, _ in parsed_entries:
        if not merged_intervals:
            merged_intervals.append((s_dt, e_dt))
        else:
            last_s, last_e = merged_intervals[-1]
            if s_dt <= last_e:
                # Overlap: extend last interval
                merged_intervals[-1] = (last_s, max(last_e, e_dt))
            else:
                merged_intervals.append((s_dt, e_dt))

    total_months = 0
    for s_dt, e_dt in merged_intervals:
        months = (e_dt.year - s_dt.year) * 12 + (e_dt.month - s_dt.month) + 1
        total_months += max(1, months)

    candidate.years_of_experience = round(total_months / 12.0, 1)
    return candidate


def validate_candidate_profile(candidate: CandidateProfile) -> CandidateProfile:
    """
    Deterministic rule-based validation of candidate profile fields.
    Flags missing email, phone, vague job titles, or unclear responsibilities.
    """
    # Email validation
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not candidate.email or not re.match(email_regex, candidate.email.strip()):
        if not candidate.email:
            candidate.ambiguities.append("Missing candidate contact email in resume.")
        else:
            candidate.ambiguities.append(f"Candidate email '{candidate.email}' appears non-standard.")

    # Phone validation
    if not candidate.phone:
        candidate.ambiguities.append("Missing direct phone number in resume.")

    # Location check
    if not candidate.location:
        candidate.ambiguities.append("Candidate physical location/residence is unspecified.")

    # Check for ambiguous job titles or missing employers
    for exp in candidate.experience:
        if not exp.company:
            candidate.ambiguities.append(f"Work experience '{exp.role or 'Unknown'}' is missing an employer/company name.")
        if exp.role:
            role_lower = exp.role.lower()
            if any(vague in role_lower for vague in ["consultant", "specialist", "freelance", "advisor"]) and "/" in role_lower:
                candidate.ambiguities.append(f"Role title '{exp.role}' at {exp.company or 'unspecified firm'} is ambiguous.")

    # De-duplicate ambiguities
    seen_ambiguities = set()
    deduped_ambiguities = []
    for amb in candidate.ambiguities:
        clean = amb.strip()
        if clean and clean not in seen_ambiguities:
            seen_ambiguities.add(clean)
            deduped_ambiguities.append(clean)
    candidate.ambiguities = deduped_ambiguities

    return candidate


def validate_hiring_evaluation(evaluation: HiringEvaluation) -> HiringEvaluation:
    """
    Deterministic validation of the generated hiring evaluation.
    Ensures required fields and schema constraints are strictly met.
    """
    if not evaluation.candidate_name or evaluation.candidate_name.strip() in ["", "null", "None"]:
        evaluation.candidate_name = "Candidate (Name Unspecified)"
        
    if not evaluation.recommended_role or evaluation.recommended_role.strip() in ["", "null", "None"]:
        evaluation.recommended_role = "Candidate Profile Review"

    if not evaluation.evaluation_summary or len(evaluation.evaluation_summary.strip()) < 20:
        evaluation.evaluation_summary = (
            f"Evaluation for {evaluation.candidate_name}. "
            f"Demonstrated background in {', '.join(evaluation.primary_skillset[:5]) if evaluation.primary_skillset else 'technical fields'}."
        )

    return evaluation


def run_evaluation_workflow(resume_text: str, preloaded_candidate: Optional[CandidateProfile] = None) -> WorkflowResult:
    """
    Central agentic orchestration workflow:
    1. Parse/Extract candidate profile (AI semantic extraction)
    2. Validate candidate profile (Deterministic validation)
    3. Analyze employment history & calculate gaps (Deterministic date math)
    4. Validate and surface ambiguities (Deterministic checks)
    5. Generate hiring evaluation (AI reasoning grounded in candidate profile)
    6. Validate evaluation schema (Deterministic validation)
    7. Generate output document PDF (Deterministic ReportLab generation)
    8. Return complete WorkflowResult
    """
    steps: list[WorkflowStep] = []
    
    try:
        # Step 1: Extract candidate profile
        if preloaded_candidate:
            candidate = preloaded_candidate
            steps.append(WorkflowStep(name="Resume parsed", status="completed", detail="Using pre-extracted candidate data."))
            steps.append(WorkflowStep(name="Candidate information extracted", status="completed", detail=f"Extracted profile for {candidate.name or 'candidate'}."))
        else:
            steps.append(WorkflowStep(name="Resume parsed", status="completed", detail=f"Extracted {len(resume_text)} characters of text."))
            candidate = extract_candidate_profile(resume_text)
            steps.append(WorkflowStep(name="Candidate information extracted", status="completed", detail=f"Extracted profile for {candidate.name or 'candidate'}."))

        # Step 2: Validate Candidate Information
        candidate = validate_candidate_profile(candidate)
        steps.append(WorkflowStep(name="Candidate profile validated", status="completed", detail="Verified required contact and profile fields."))

        # Step 3: Analyze employment history & detect gaps deterministically
        candidate = calculate_employment_history_and_gaps(candidate)
        steps.append(WorkflowStep(name="Employment history analyzed", status="completed", detail=f"Calculated ~{candidate.years_of_experience or 0} years experience."))
        
        gap_count = len(candidate.employment_gaps)
        steps.append(WorkflowStep(name="Gaps checked", status="completed", detail=f"Identified {gap_count} employment gap(s)."))

        # Step 4: Generate Corporate Hiring Evaluation
        evaluation = generate_hiring_evaluation(candidate, resume_text)
        steps.append(WorkflowStep(name="Evaluation generated", status="completed", detail=f"Recommended role: {evaluation.recommended_role}."))

        # Step 5: Validate evaluation
        evaluation = validate_hiring_evaluation(evaluation)
        steps.append(WorkflowStep(name="Evaluation validated", status="completed", detail="Validated evaluation structure against corporate hiring standards."))

        # Step 6: Generate Downloadable PDF
        pdf_path, pdf_filename = generate_evaluation_pdf(evaluation)
        steps.append(WorkflowStep(name="PDF generated", status="completed", detail=f"Generated {pdf_filename}."))

        # Step 7: Dispatch Ready
        steps.append(WorkflowStep(name="Dispatch ready", status="completed", detail="Evaluation ready for automated mock dispatch to HR."))

        return WorkflowResult(
            success=True,
            candidate=candidate,
            evaluation=evaluation,
            pdf_path=str(pdf_path),
            pdf_filename=pdf_filename,
            steps=steps,
        )

    except Exception as exc:
        logger.error(f"Error in evaluation workflow: {exc}", exc_info=True)
        # Return partial failure result with error
        return WorkflowResult(
            success=False,
            candidate=preloaded_candidate or CandidateProfile(raw_text=resume_text),
            evaluation=HiringEvaluation(
                candidate_name="Evaluation Failed",
                recommended_role="N/A",
                evaluation_summary=f"Workflow failed: {exc}",
            ),
            steps=steps,
            error=str(exc),
        )
