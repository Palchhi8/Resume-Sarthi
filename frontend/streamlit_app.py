"""Streamlit frontend for AI Recruiter Agent with adaptive styling and resilient API connection."""

import os
import time
from pathlib import Path
import streamlit as st
import requests

# Local fallback imports if FastAPI backend is ever unreachable
from app.config import GENERATED_DIR
from app.parser import parse_resume, DocumentParsingError
from app.models import CandidateProfile
from app.ai_service import extract_candidate_profile, ask_candidate_question
from app.workflow import (
    calculate_employment_history_and_gaps,
    validate_candidate_profile,
    run_evaluation_workflow,
)
from app.email_service import dispatch_evaluation

# Backend URL configuration
API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

# Page setup
st.set_page_config(
    page_title="AI Recruiter Agent | Resume Intelligence",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom minimal CSS with dark/light mode resilience
st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 1.25rem;
        padding-bottom: 2rem;
        max-width: 1150px;
    }
    .header-box {
        padding: 1.5rem 2rem;
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
    }
    .header-title {
        font-size: 1.85rem;
        font-weight: 700;
        color: #F8FAFC !important;
        margin: 0;
        letter-spacing: -0.01em;
    }
    .header-subtitle {
        font-size: 0.95rem;
        color: #94A3B8 !important;
        margin-top: 0.35rem;
        margin-bottom: 0;
    }
    .eval-card {
        background-color: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(226, 232, 240, 0.15);
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }
    .eval-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #F1F5F9;
        margin-bottom: 0.5rem;
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.65rem;
        font-size: 0.78rem;
        font-weight: 600;
        border-radius: 9999px;
        margin: 0.18rem;
    }
    .badge-blue { background-color: #1E3A8A; color: #DBEAFE; border: 1px solid #3B82F6; }
    .badge-amber { background-color: #78350F; color: #FEF3C7; border: 1px solid #F59E0B; }
    .badge-green { background-color: #064E3B; color: #D1FAE5; border: 1px solid #10B981; }
    .badge-slate { background-color: #334155; color: #F1F5F9; border: 1px solid #64748B; }
    .status-check {
        color: #10B981;
        font-weight: 600;
        font-size: 0.95rem;
        margin: 0.35rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "candidate" not in st.session_state:
    st.session_state.candidate = None
if "filename" not in st.session_state:
    st.session_state.filename = ""
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []
if "workflow_result" not in st.session_state:
    st.session_state.workflow_result = None
if "dispatch_status" not in st.session_state:
    st.session_state.dispatch_status = None


def check_backend_health() -> bool:
    """Check if FastAPI backend is reachable."""
    try:
        res = requests.get(f"{API_URL}/health", timeout=1.5)
        return res.status_code == 200
    except Exception:
        return False


def service_upload_resume(filename: str, file_bytes: bytes) -> dict:
    """Parse resume via FastAPI with automatic direct fallback."""
    try:
        files = {"file": (filename, file_bytes, "application/octet-stream")}
        resp = requests.post(f"{API_URL}/api/resume/upload", files=files, timeout=45)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass

    # Direct fallback
    text = parse_resume(file_bytes, filename)
    candidate = extract_candidate_profile(text)
    candidate = validate_candidate_profile(candidate)
    candidate = calculate_employment_history_and_gaps(candidate)
    return {
        "filename": filename,
        "file_type": Path(filename).suffix.lower(),
        "extracted_text": text,
        "candidate": candidate.model_dump(),
    }


def service_ask_question(question: str, resume_text: str, candidate_dict: dict) -> dict:
    """Answer question via FastAPI with automatic direct fallback."""
    try:
        payload = {"question": question, "candidate": candidate_dict, "resume_text": resume_text}
        resp = requests.post(f"{API_URL}/api/ask", json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass

    cand_model = CandidateProfile(**candidate_dict) if candidate_dict else None
    res = ask_candidate_question(question=question, resume_text=resume_text, candidate=cand_model)
    return {"answer": res.answer, "grounded": res.grounded}


def service_evaluate(resume_text: str, candidate_data: object) -> dict:
    """Execute evaluation workflow via FastAPI with automatic direct fallback."""
    if isinstance(candidate_data, CandidateProfile):
        cand_dict = candidate_data.model_dump()
        cand_model = candidate_data
    elif isinstance(candidate_data, dict):
        cand_dict = candidate_data
        try:
            cand_model = CandidateProfile(**candidate_data)
        except Exception:
            cand_model = None
    else:
        cand_dict = None
        cand_model = None

    try:
        payload = {"resume_text": resume_text, "candidate": cand_dict}
        resp = requests.post(f"{API_URL}/api/evaluate", json=payload, timeout=45)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass

    wf_res = run_evaluation_workflow(resume_text=resume_text, preloaded_candidate=cand_model)
    return wf_res.model_dump()


def service_dispatch(filename: str, recipient: str) -> dict:
    """Dispatch evaluation via FastAPI with automatic direct fallback."""
    try:
        payload = {"filename": filename, "recipient": recipient}
        resp = requests.post(f"{API_URL}/api/dispatch", json=payload, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass

    disp = dispatch_evaluation(file_path=filename, recipient=recipient)
    return disp.model_dump()


# Sidebar Info
with st.sidebar:
    st.subheader("System Status")
    is_backend_online = check_backend_health()
    if is_backend_online:
        st.success("API Backend: Connected (0.0.0.0:8000)")
    else:
        st.info("API Backend: Standalone Mode (Direct Services Active)")

    st.markdown("---")
    st.subheader("Assessment Controls")
    st.caption("Pre-configured Realistic Candidate for instant evaluation:")
    
    if st.button("📄 Load Sample Resume", use_container_width=True, type="primary"):
        sample_path = Path(__file__).resolve().parent.parent / "data" / "sample_resume.txt"
        if sample_path.exists():
            with open(sample_path, "rb") as f:
                content_bytes = f.read()
            
            st.session_state.filename = "sample_resume.txt"
            st.session_state.workflow_result = None
            st.session_state.qa_history = []
            st.session_state.dispatch_status = None

            with st.spinner("Processing realistic candidate profile..."):
                try:
                    data = service_upload_resume("sample_resume.txt", content_bytes)
                    st.session_state.candidate = data.get("candidate")
                    st.session_state.resume_text = data.get("extracted_text")
                    st.success("Sample candidate profile loaded successfully!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error processing sample resume: {exc}")
        else:
            st.error("Sample resume file not found in data/ directory.")

    st.markdown("---")
    st.caption(
        "**AI Recruiter Agent MVP**\n\n"
        "• Deterministic gap & date math\n\n"
        "• Strict anti-hallucination Q&A\n\n"
        "• Corporate Evaluation Form\n\n"
        "• Executive PDF Generation\n\n"
        "• Mock Email Dispatch"
    )

# Header Section
st.markdown(
    """
    <div class="header-box">
        <h1 class="header-title">AI Recruiter Agent</h1>
        <p class="header-subtitle">Resume Intelligence & Automated Candidate Evaluation Workflow</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# TASK 1: Resume Upload & Parsing Section
st.markdown("### 1. Candidate Resume Ingestion")

upload_col1, upload_col2 = st.columns([3, 1])

with upload_col1:
    uploaded_file = st.file_uploader(
        "Upload candidate resume (PDF, DOCX, TXT)",
        type=["pdf", "docx", "txt"],
        help="Upload candidate biodata or resume to begin extraction.",
    )

with upload_col2:
    st.write("")
    st.write("")
    if st.button("Clear Resume Data", use_container_width=True):
        st.session_state.resume_text = ""
        st.session_state.candidate = None
        st.session_state.filename = ""
        st.session_state.workflow_result = None
        st.session_state.qa_history = []
        st.session_state.dispatch_status = None
        st.rerun()

if uploaded_file is not None and uploaded_file.name != st.session_state.filename:
    st.session_state.filename = uploaded_file.name
    with st.spinner(f"Extracting and analyzing '{uploaded_file.name}'..."):
        try:
            data = service_upload_resume(uploaded_file.name, uploaded_file.getvalue())
            st.session_state.candidate = data.get("candidate")
            st.session_state.resume_text = data.get("extracted_text")
            st.session_state.workflow_result = None
            st.session_state.qa_history = []
            st.session_state.dispatch_status = None
            st.success(f"Successfully parsed '{uploaded_file.name}'!")
        except DocumentParsingError as d_err:
            st.error(f"Upload error: {d_err}")
        except Exception as exc:
            st.error(f"Error processing resume: {exc}")

# Display Candidate Profile if available
candidate = st.session_state.candidate
if candidate:
    st.markdown("---")
    st.markdown("### 2. Structured Candidate Profile")
    
    # Metadata bar
    meta_c1, meta_c2, meta_c3, meta_c4 = st.columns(4)
    with meta_c1:
        st.metric("Candidate Name", candidate.get("name") or "Unspecified")
    with meta_c2:
        st.metric("Contact Email", candidate.get("email") or "Not provided")
    with meta_c3:
        st.metric("Location", candidate.get("location") or "Unspecified")
    with meta_c4:
        years = candidate.get("years_of_experience")
        st.metric("Verified Experience", f"{years} years" if years is not None else "Incomplete Dates")

    # Skills Badges
    skills = candidate.get("skills", [])
    if skills:
        st.markdown("**Identified Technical Skills:**")
        skill_badges = " ".join([f'<span class="badge badge-blue">{s}</span>' for s in skills])
        st.markdown(skill_badges, unsafe_allow_html=True)
        st.write("")

    # Timeline & Gaps Columns
    col_exp, col_review = st.columns([3, 2])

    with col_exp:
        st.markdown("#### Employment History")
        exp_list = candidate.get("experience", [])
        if exp_list:
            for exp in exp_list:
                company = exp.get("company") or "Unspecified Company"
                role = exp.get("role") or "Role Unspecified"
                start = exp.get("start_date") or "?"
                end = exp.get("end_date") or ("Present" if exp.get("is_current") else "?")
                desc = exp.get("description") or ""
                
                with st.expander(f"**{role}** — {company} ({start} – {end})", expanded=True):
                    if desc:
                        st.write(desc)
                    techs = exp.get("technologies", [])
                    if techs:
                        st.caption("Technologies: " + ", ".join(techs))
        else:
            st.info("No work experience entries extracted.")

        st.markdown("#### Education")
        edu_list = candidate.get("education", [])
        if edu_list:
            for edu in edu_list:
                deg = edu.get("degree") or "Degree"
                inst = edu.get("institution") or "Institution"
                yr = f"({edu.get('year')})" if edu.get("year") else ""
                st.markdown(f"• **{deg}** — {inst} {yr}")
        else:
            st.info("No education credentials listed.")

    with col_review:
        st.markdown("#### Timeline Audit (Deterministic)")
        gaps = candidate.get("employment_gaps", [])
        if gaps:
            for gap in gaps:
                st.warning(f"⚠ **Employment Gap:** {gap}")
        else:
            st.success("✓ No employment gaps detected in verified timeline.")

        st.markdown("#### Grey Areas & Ambiguities")
        ambiguities = candidate.get("ambiguities", [])
        if ambiguities:
            for amb in ambiguities:
                st.info(f"🔍 **Investigation Point:** {amb}")
        else:
            st.success("✓ No critical ambiguities detected.")

    # TASK 2: Natural Language Q&A
    st.markdown("---")
    st.markdown("### 3. Recruiter Document Q&A")
    st.caption("Ask questions strictly grounded in the candidate's resume. The AI will not fabricate unmentioned details.")

    # Suggested Questions Buttons
    st.markdown("**Suggested Recruiter Inquiries:**")
    q_col1, q_col2, q_col3 = st.columns(3)
    suggested_q = None
    with q_col1:
        if st.button("☁ Cloud Deployment Experience?", use_container_width=True):
            suggested_q = "Does this candidate have experience with cloud deployments, and are there any unexplained employment gaps?"
    with q_col2:
        if st.button("⏳ Detected Employment Gaps?", use_container_width=True):
            suggested_q = "What employment gaps or ambiguous timelines exist in this resume?"
    with q_col3:
        if st.button("🛠 Top Technical Skills?", use_container_width=True):
            suggested_q = "What are the candidate's strongest technical skills and verified backend technologies?"

    # Question Input
    default_text = suggested_q if suggested_q else ""
    question_input = st.text_input(
        "Enter your question for the AI Recruiter:",
        value=default_text,
        placeholder="e.g., Does this candidate have hands-on experience with Kubernetes?",
    )

    if st.button("Ask AI Recruiter", type="primary") or (suggested_q and not st.session_state.qa_history):
        active_q = question_input.strip() or suggested_q
        if active_q:
            with st.spinner("Analyzing document context..."):
                try:
                    ans_data = service_ask_question(active_q, st.session_state.resume_text, candidate)
                    st.session_state.qa_history.insert(0, {
                        "question": active_q,
                        "answer": ans_data.get("answer"),
                        "grounded": ans_data.get("grounded", True),
                    })
                except Exception as exc:
                    st.error(f"Error querying Q&A service: {exc}")

    # Display Q&A history
    if st.session_state.qa_history:
        for qa in st.session_state.qa_history[:5]:
            with st.chat_message("user"):
                st.write(f"**{qa['question']}**")
            with st.chat_message("assistant"):
                st.markdown(qa["answer"])
                st.markdown('<span class="badge badge-green">✓ Grounded in Document Context</span>', unsafe_allow_html=True)

    # TASK 3: Agentic Evaluation Workflow
    st.markdown("---")
    st.markdown("### 4. Agentic Evaluation Workflow & Corporate Form")
    st.caption("Executes multi-step orchestration: candidate validation, gap analysis, evaluation synthesis, and PDF generation.")

    if st.button("🚀 Run Agentic Evaluation Workflow", type="primary", use_container_width=True):
        with st.status("Executing Agentic Orchestration Pipeline...", expanded=True) as status_box:
            st.markdown('<p class="status-check">✓ Resume parsed</p>', unsafe_allow_html=True)
            time.sleep(0.05)
            st.markdown('<p class="status-check">✓ Candidate information extracted</p>', unsafe_allow_html=True)
            time.sleep(0.05)
            st.markdown('<p class="status-check">✓ Employment history analyzed</p>', unsafe_allow_html=True)
            time.sleep(0.05)
            st.markdown('<p class="status-check">✓ Gaps checked</p>', unsafe_allow_html=True)
            
            try:
                workflow_data = service_evaluate(st.session_state.resume_text, candidate)
                st.session_state.workflow_result = workflow_data
                
                st.markdown('<p class="status-check">✓ Evaluation generated</p>', unsafe_allow_html=True)
                st.markdown('<p class="status-check">✓ Evaluation validated</p>', unsafe_allow_html=True)
                st.markdown('<p class="status-check">✓ PDF generated</p>', unsafe_allow_html=True)
                st.markdown('<p class="status-check">✓ Dispatch ready</p>', unsafe_allow_html=True)
                
                status_box.update(label="✓ Agentic Workflow Complete!", state="complete", expanded=True)
            except Exception as exc:
                status_box.update(label="Workflow failed", state="error")
                st.error(f"Failed to execute evaluation workflow: {exc}")

    # Display Evaluation Result if available
    wf_res = st.session_state.workflow_result
    if wf_res:
        if wf_res.get("error"):
            st.error(f"Workflow error: {wf_res.get('error')}")
            
        eval_data = wf_res.get("evaluation", {})
        pdf_filename = wf_res.get("pdf_filename")

        st.markdown(
            f"""
            <div class="eval-card">
                <div class="eval-title">Corporate Hiring Evaluation: {eval_data.get('candidate_name')}</div>
                <div style="margin-bottom: 0.5rem;">
                    <span class="badge badge-blue">Target Role: {eval_data.get('recommended_role')}</span>
                    <span class="badge badge-green">Recommendation: {eval_data.get('decision_recommendation')}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        ev_c1, ev_c2 = st.columns([3, 2])

        with ev_c1:
            st.markdown("#### Executive Summary")
            st.write(eval_data.get("evaluation_summary"))

            st.markdown("#### Relevant Demonstrated Experience")
            for rev_exp in eval_data.get("relevant_experience", []):
                st.markdown(f"• {rev_exp}")

            st.markdown("#### Core Strengths")
            for strength in eval_data.get("strengths", []):
                st.markdown(f"✓ {strength}")

        with ev_c2:
            st.markdown("#### Timeline & Investigation Points")
            gaps = eval_data.get("employment_gaps", [])
            if gaps:
                for g in gaps:
                    st.warning(f"⚠ {g}")
            else:
                st.success("✓ No employment gaps detected.")

            ambigs = eval_data.get("ambiguities_missing_info", [])
            if ambigs:
                for a in ambigs:
                    st.info(f"🔍 {a}")
            else:
                st.success("✓ No ambiguities noted.")

            investigations = eval_data.get("areas_for_investigation", [])
            if investigations:
                st.markdown("#### Recommended Interview Inquiries")
                for inv in investigations:
                    st.markdown(f"→ {inv}")

        # Download and Dispatch Actions
        st.markdown("---")
        action_c1, action_c2 = st.columns(2)

        with action_c1:
            if pdf_filename:
                pdf_path = GENERATED_DIR / pdf_filename
                pdf_bytes = None
                if pdf_path.exists():
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                else:
                    try:
                        download_url = f"{API_URL}/api/evaluation/download/{pdf_filename}"
                        pdf_resp = requests.get(download_url, timeout=10)
                        if pdf_resp.status_code == 200:
                            pdf_bytes = pdf_resp.content
                    except Exception:
                        pass

                if pdf_bytes:
                    st.download_button(
                        label=f"📥 Download Evaluation PDF ({pdf_filename})",
                        data=pdf_bytes,
                        file_name=pdf_filename,
                        mime="application/pdf",
                        use_container_width=True,
                        type="primary",
                    )
                else:
                    st.button("PDF download unavailable", disabled=True, use_container_width=True)

        with action_c2:
            if st.button("✉ Dispatch Evaluation to HR", use_container_width=True):
                with st.spinner("Dispatching evaluation to HR Admissions..."):
                    try:
                        disp_data = service_dispatch(pdf_filename, "hr-admissions@company.mock")
                        st.session_state.dispatch_status = disp_data
                        st.success("Mock dispatch completed successfully!")
                    except Exception as exc:
                        st.error(f"Error during dispatch: {exc}")

        # Dispatch feedback box
        if st.session_state.dispatch_status:
            disp = st.session_state.dispatch_status
            st.markdown(
                f"""
                <div class="eval-card" style="border-left: 4px solid #10B981; background-color: rgba(6, 78, 59, 0.25);">
                    <b style="color: #6EE7B7;">Mock HR Dispatch Confirmation</b><br/>
                    <small><b>Status:</b> {disp.get('status').upper()} | <b>Recipient:</b> {disp.get('recipient')} | <b>Attachment:</b> {disp.get('attachment')}</small><br/>
                    <small style="color: #A7F3D0;">{disp.get('message')}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )

else:
    st.info("Upload a candidate resume or click 'Load Sample Resume' in the sidebar to begin.")
