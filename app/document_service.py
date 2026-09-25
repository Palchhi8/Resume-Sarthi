"""Document generation service creating Corporate Hiring Evaluation PDFs using ReportLab."""

import re
import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from app.config import GENERATED_DIR
from app.models import HiringEvaluation


def sanitize_filename(name: str) -> str:
    """Sanitize candidate name for safe filesystem usage."""
    clean = re.sub(r"[^\w\s-]", "", name).strip()
    return re.sub(r"[-\s]+", "_", clean) or "Candidate"


def generate_evaluation_pdf(evaluation: HiringEvaluation) -> tuple[Path, str]:
    """
    Generate an executive-ready Corporate Hiring Evaluation PDF.
    Returns (Path, filename).
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = sanitize_filename(evaluation.candidate_name)
    filename = f"Evaluation_{safe_name}_{timestamp}.pdf"
    file_path = GENERATED_DIR / filename

    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=12,
    )

    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=10,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
    )

    body_bold = ParagraphStyle(
        "DocBodyBold",
        parent=body_style,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0F172A"),
    )

    bullet_style = ParagraphStyle(
        "DocBullet",
        parent=body_style,
        leftIndent=12,
        spaceAfter=3,
    )

    warning_bullet_style = ParagraphStyle(
        "DocWarningBullet",
        parent=body_style,
        leftIndent=12,
        textColor=colors.HexColor("#B91C1C"),
        spaceAfter=3,
    )

    elements = []

    # Title & Metadata
    elements.append(Paragraph("CORPORATE CANDIDATE EVALUATION", title_style))
    elements.append(
        Paragraph(
            f"AI-Powered Recruiter Intelligence & Automated Assessment • Generated: {datetime.datetime.now().strftime('%B %d, %Y - %H:%M')}",
            subtitle_style,
        )
    )
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=12))

    # Candidate Overview Table
    years_exp = f"{evaluation.years_of_experience:.1f} years" if evaluation.years_of_experience is not None else "Unspecified / Incomplete Dates"
    overview_data = [
        [
            Paragraph("<b>Candidate Name:</b>", body_style),
            Paragraph(evaluation.candidate_name, body_bold),
            Paragraph("<b>Recommended Role:</b>", body_style),
            Paragraph(f"<b>{evaluation.recommended_role}</b>", body_bold),
        ],
        [
            Paragraph("<b>Contact Email:</b>", body_style),
            Paragraph(evaluation.email or "Not listed", body_style),
            Paragraph("<b>Years of Experience:</b>", body_style),
            Paragraph(years_exp, body_style),
        ],
        [
            Paragraph("<b>Decision Status:</b>", body_style),
            Paragraph(f"<b>{evaluation.decision_recommendation}</b>", body_bold),
            Paragraph("<b>Primary Skills:</b>", body_style),
            Paragraph(", ".join(evaluation.primary_skillset[:6]) or "None listed", body_style),
        ],
    ]

    overview_table = Table(overview_data, colWidths=[1.4 * inch, 2.2 * inch, 1.5 * inch, 2.4 * inch])
    overview_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    elements.append(overview_table)
    elements.append(Spacer(1, 12))

    # Evaluation Summary
    elements.append(Paragraph("Executive Evaluation Summary", section_header_style))
    elements.append(Paragraph(evaluation.evaluation_summary.replace("\n", "<br/>"), body_style))
    elements.append(Spacer(1, 10))

    # Education & Relevant Experience
    elements.append(Paragraph("Education & Credentials", section_header_style))
    if evaluation.education:
        for edu in evaluation.education:
            elements.append(Paragraph(f"• {edu}", bullet_style))
    else:
        elements.append(Paragraph("• No formal education listed in resume.", bullet_style))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Relevant Experience & Demonstrated Achievements", section_header_style))
    if evaluation.relevant_experience:
        for exp_item in evaluation.relevant_experience:
            elements.append(Paragraph(f"• {exp_item}", bullet_style))
    else:
        elements.append(Paragraph("• See parsed chronological history in system.", bullet_style))
    elements.append(Spacer(1, 8))

    # Key Strengths
    if evaluation.strengths:
        elements.append(Paragraph("Core Candidate Strengths", section_header_style))
        for strength in evaluation.strengths:
            elements.append(Paragraph(f"✓ {strength}", bullet_style))
        elements.append(Spacer(1, 8))

    # Critical Review: Employment Gaps & Ambiguities
    elements.append(Paragraph("Verified Employment Gaps (Date-Calculated)", section_header_style))
    if evaluation.employment_gaps:
        for gap in evaluation.employment_gaps:
            elements.append(Paragraph(f"⚠ {gap}", warning_bullet_style))
    else:
        elements.append(Paragraph("✓ No employment gaps detected in verified timeline.", bullet_style))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Ambiguities & Grey Areas (To Investigate)", section_header_style))
    if evaluation.ambiguities_missing_info:
        for amb in evaluation.ambiguities_missing_info:
            elements.append(Paragraph(f"? {amb}", warning_bullet_style))
    else:
        elements.append(Paragraph("✓ No critical ambiguities or missing contact information detected.", bullet_style))
    elements.append(Spacer(1, 8))

    if evaluation.areas_for_investigation:
        elements.append(Paragraph("Recommended Recruiter Follow-Up Questions", section_header_style))
        for q in evaluation.areas_for_investigation:
            elements.append(Paragraph(f"→ {q}", bullet_style))
        elements.append(Spacer(1, 10))

    # Footer note
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceAfter=8))
    elements.append(
        Paragraph(
            "CONFIDENTIAL: This evaluation was prepared by AI Recruiter Agent using strictly grounded document analysis. "
            "All findings and calculated gaps should be reviewed by a human recruiter during interview screening.",
            ParagraphStyle(
                "DocFooter",
                parent=styles["Normal"],
                fontName="Helvetica-Oblique",
                fontSize=8,
                textColor=colors.HexColor("#94A3B8"),
            ),
        )
    )

    doc.build(elements)
    return file_path, filename


def generate_evaluation_text(evaluation: HiringEvaluation) -> str:
    """Generate clean plain text fallback for evaluation report."""
    years_exp = f"{evaluation.years_of_experience:.1f} years" if evaluation.years_of_experience is not None else "Unspecified"
    lines = [
        "=" * 70,
        "CORPORATE CANDIDATE EVALUATION REPORT",
        "=" * 70,
        f"Candidate Name:         {evaluation.candidate_name}",
        f"Email:                  {evaluation.email or 'Not specified'}",
        f"Recommended Role:       {evaluation.recommended_role}",
        f"Decision Recommendation:{evaluation.decision_recommendation}",
        f"Years of Experience:    {years_exp}",
        f"Primary Skillset:       {', '.join(evaluation.primary_skillset)}",
        "-" * 70,
        "EXECUTIVE EVALUATION SUMMARY:",
        evaluation.evaluation_summary,
        "-" * 70,
        "EDUCATION:",
    ]
    for edu in evaluation.education or ["None listed"]:
        lines.append(f"  * {edu}")
    lines.append("-" * 70)
    lines.append("RELEVANT EXPERIENCE:")
    for exp in evaluation.relevant_experience or ["None listed"]:
        lines.append(f"  * {exp}")
    lines.append("-" * 70)
    lines.append("EMPLOYMENT Gaps (Date-Calculated):")
    for gap in evaluation.employment_gaps or ["No employment gaps detected."]:
        lines.append(f"  [!] {gap}")
    lines.append("-" * 70)
    lines.append("AMBIGUITIES & MISSING INFORMATION:")
    for amb in evaluation.ambiguities_missing_info or ["None identified."]:
        lines.append(f"  [?] {amb}")
    lines.append("-" * 70)
    lines.append("AREAS FOR INVESTIGATION / INTERVIEW QUESTIONS:")
    for area in evaluation.areas_for_investigation or ["Standard technical assessment."]:
        lines.append(f"  -> {area}")
    lines.append("=" * 70)
    return "\n".join(lines)
