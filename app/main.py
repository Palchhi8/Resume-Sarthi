"""FastAPI application providing endpoints for resume parsing, Q&A, agentic evaluation, and dispatch."""

import logging
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from app.config import (
    MAX_UPLOAD_SIZE_BYTES,
    SUPPORTED_EXTENSIONS,
    GENERATED_DIR,
)
from app.models import (
    AskRequest,
    AskResponse,
    UploadResponse,
    EvaluateRequest,
    DispatchRequest,
    DispatchResponse,
    WorkflowResult,
)
from app.parser import parse_resume, DocumentParsingError
from app.ai_service import extract_candidate_profile, ask_candidate_question
from app.workflow import (
    calculate_employment_history_and_gaps,
    validate_candidate_profile,
    run_evaluation_workflow,
)
from app.email_service import dispatch_evaluation

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("recruiter-app")

app = FastAPI(
    title="AI Recruiter Agent API",
    description="Resume Intelligence & Agentic Candidate Evaluation Backend",
    version="1.0.0",
)

# Enable CORS for local Streamlit interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["System"])
def health_check() -> dict:
    """Service health check endpoint."""
    return {
        "status": "ok",
        "app": "AI Recruiter Agent",
        "version": "1.0.0",
    }


@app.post("/api/resume/upload", response_model=UploadResponse, tags=["Resume"])
async def upload_resume(file: UploadFile = File(...)) -> UploadResponse:
    """
    Upload and parse candidate resume (.pdf, .docx, or .txt).
    Extracts structured candidate profile and performs deterministic validation and gap analysis.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing.",
        )

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Allowed formats: {', '.join(SUPPORTED_EXTENSIONS)}.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    try:
        extracted_text = parse_resume(file_bytes, file.filename)
    except DocumentParsingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Unexpected error parsing document: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while parsing the document text.",
        )

    try:
        # Step 1: AI semantic extraction
        candidate = extract_candidate_profile(extracted_text)
        # Step 2: Deterministic validation & date math
        candidate = validate_candidate_profile(candidate)
        candidate = calculate_employment_history_and_gaps(candidate)
        
        return UploadResponse(
            filename=file.filename,
            file_type=file_ext,
            extracted_text=extracted_text,
            candidate=candidate,
        )
    except RuntimeError as exc:
        # e.g. Missing OpenAI API key
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error extracting candidate profile: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting candidate profile: {exc}",
        )


@app.post("/api/ask", response_model=AskResponse, tags=["Q&A"])
def ask_question(request: AskRequest) -> AskResponse:
    """
    Recruiter natural-language Q&A endpoint.
    Answers strictly grounded in candidate resume and structured profile.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    if not request.resume_text or not request.resume_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume text is required for context.",
        )

    try:
        return ask_candidate_question(
            question=request.question,
            resume_text=request.resume_text,
            candidate=request.candidate,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error answering recruiter question: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing question: {exc}",
        )


@app.post("/api/evaluate", response_model=WorkflowResult, tags=["Evaluation"])
def evaluate_candidate(request: EvaluateRequest) -> WorkflowResult:
    """
    Execute full agentic evaluation workflow:
    Parse/Extract -> Validate -> History/Gaps -> Ambiguities -> Generate Evaluation -> Validate -> PDF Generation.
    """
    if not request.resume_text or not request.resume_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume text cannot be empty.",
        )

    try:
        result = run_evaluation_workflow(
            resume_text=request.resume_text,
            preloaded_candidate=request.candidate,
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error running evaluation workflow: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {exc}",
        )


@app.post("/api/dispatch", response_model=DispatchResponse, tags=["Dispatch"])
def dispatch_to_hr(request: DispatchRequest) -> DispatchResponse:
    """
    Mock email dispatch endpoint sending evaluation to HR admissions.
    """
    try:
        target_path = request.file_path
        if not target_path and request.filename:
            target_path = str(GENERATED_DIR / request.filename)

        response = dispatch_evaluation(
            file_path=target_path,
            recipient=request.recipient,
        )
        return response
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error in email dispatch: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dispatch evaluation: {exc}",
        )


@app.get("/api/evaluation/download/{filename}", tags=["Download"])
def download_evaluation(filename: str):
    """
    Download generated evaluation file.
    Includes path sanitization to prevent directory traversal.
    """
    safe_name = Path(filename).name
    file_path = (GENERATED_DIR / safe_name).resolve()

    # Directory traversal prevention
    if not str(file_path).startswith(str(GENERATED_DIR.resolve())):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename path.",
        )

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation file '{safe_name}' not found.",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=safe_name,
    )
