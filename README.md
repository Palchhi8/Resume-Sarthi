# AI Recruiter Agent

> AI-powered resume intelligence and agentic candidate evaluation workflow.

## 1. Overview

AI Recruiter Agent is a web-based AI application that automates the initial candidate evaluation workflow from resume ingestion to HR evaluation and dispatch.

The system allows a recruiter to:

1. Upload a candidate resume.
2. Automatically extract and structure candidate information.
3. Ask natural-language questions about the candidate.
4. Generate a structured corporate hiring evaluation.
5. Identify employment gaps and ambiguities.
6. Generate a downloadable evaluation document.
7. Simulate dispatching the completed evaluation to HR.

The application is designed as a focused assessment MVP with a clean architecture and deployment-ready configuration.

---

# 2. Problem Statement

Recruiters often spend significant time manually reviewing resumes, identifying technical skills, understanding employment history, checking potential gaps, answering questions about candidates, and filling internal evaluation forms.

This project demonstrates how an AI-assisted workflow can automate these repetitive steps while keeping the recruiter in control.

The system combines:

* Document parsing
* Structured information extraction
* Natural-language AI interaction
* Deterministic employment analysis
* AI-powered evaluation generation
* Structured validation
* Document generation
* Automated dispatch simulation

---

# 3. Solution

The application follows this workflow:

```text
Candidate Resume
       │
       ▼
Resume Upload
       │
       ▼
Document Parser
       │
       ▼
AI Candidate Extraction
       │
       ▼
Structured Candidate Profile
       │
       ├──────────────────────┐
       ▼                      ▼
Natural Language Q&A    Evaluation Workflow
       │                      │
       │                      ▼
       │               Employment Analysis
       │                      │
       │                      ▼
       │               Gap / Ambiguity Detection
       │                      │
       │                      ▼
       │               Hiring Evaluation
       │                      │
       │                      ▼
       │                 Validation
       │                      │
       │                      ▼
       │                 PDF Generation
       │                      │
       │                      ▼
       │                 HR Dispatch
       │
       ▼
Recruiter Answer
```

---

# 4. Assessment Requirements Covered

| Assessment Requirement      | Implementation                      |
| --------------------------- | ----------------------------------- |
| Resume/Biodata upload       | PDF, DOCX and TXT upload            |
| Mock input                  | Fictional sample resume included    |
| Resume parsing              | PyMuPDF / python-docx / TXT parser  |
| AI extraction               | OpenAI API                          |
| Natural-language Q&A        | Grounded recruiter Q&A              |
| Context-aware answers       | Resume + structured profile context |
| Hallucination prevention    | Grounded prompts + validation       |
| Employment gap detection    | Programmatic date analysis          |
| Corporate evaluation form   | Structured Pydantic model           |
| Automated form generation   | Evaluation workflow                 |
| Downloadable output         | PDF + structured JSON               |
| Email dispatch              | Mock SMTP/dispatch workflow         |
| System design documentation | Included below                      |
| Prompt strategy             | Included below                      |
| Future improvements         | Included below                      |
| Deployment readiness        | Docker + environment configuration  |

---

# 5. Key Features

## Resume Upload

Recruiters can upload:

* PDF
* DOCX
* TXT

The system extracts readable text and passes it to the candidate intelligence pipeline.

---

## Candidate Information Extraction

The AI converts unstructured resume information into a structured candidate profile.

Example:

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "skills": [
    "Python",
    "FastAPI",
    "AWS",
    "Docker"
  ],
  "experience": [],
  "education": [],
  "employment_gaps": [],
  "ambiguities": []
}
```

The actual output is validated using Pydantic models.

---

# 6. Natural Language Q&A

Recruiters can ask questions such as:

```text
Does this candidate have experience with cloud deployments?

Are there any unexplained employment gaps?

What are the candidate's strongest technical skills?

How many years of relevant experience does the candidate have?

Does the resume mention AWS services?
```

The AI answers using only the uploaded candidate information.

If information is missing, the system explicitly communicates that the resume does not provide enough information.

---

# 7. Agentic Workflow

The agentic component automatically performs the candidate evaluation workflow.

```text
START
  │
  ▼
Parse Resume
  │
  ▼
Extract Candidate Information
  │
  ▼
Validate Candidate Profile
  │
  ▼
Analyze Employment History
  │
  ▼
Identify Gaps & Ambiguities
  │
  ▼
Generate Hiring Evaluation
  │
  ▼
Validate Evaluation
  │
  ▼
Generate PDF
  │
  ▼
Prepare HR Dispatch
  │
  ▼
END
```

The workflow is orchestrated by application code rather than relying on a single unrestricted LLM response.

---

# 8. Corporate Hiring Evaluation

The generated evaluation contains:

* Candidate Name
* Email
* Primary Skillset
* Years of Experience
* Education
* Relevant Experience
* Employment Gaps
* Ambiguities / Missing Information
* Recommended Role
* Evaluation Summary

Example:

```json
{
  "candidate_name": "John Doe",
  "email": "john@example.com",
  "primary_skillset": [
    "Python",
    "FastAPI",
    "AWS",
    "Docker"
  ],
  "years_of_experience": 4.2,
  "education": [
    "B.Tech Computer Science"
  ],
  "relevant_experience": [
    "Backend API development",
    "Cloud deployment",
    "Containerization"
  ],
  "employment_gaps": [],
  "ambiguities": [
    "Specific AWS services are not specified in the resume."
  ],
  "recommended_role": "Backend Engineer",
  "evaluation_summary": "Candidate demonstrates relevant backend development experience..."
}
```

The exact output depends on the uploaded resume.

---

# 9. Prompt Strategy

The AI prompts are intentionally separated according to responsibility.

## Extraction Prompt

Responsible for:

```text
Resume
   ↓
Structured Candidate Profile
```

The model is instructed to:

* use only the resume
* preserve factual information
* avoid fabrication
* identify ambiguity
* avoid filling missing fields with assumptions
* return structured information

---

## Q&A Prompt

Responsible for:

```text
Resume + Candidate Profile + Question
                ↓
         Grounded Answer
```

The model is explicitly instructed:

```text
Answer only using the supplied candidate resume
and structured candidate profile.

Never invent candidate information.

Do not use external knowledge about the candidate.

If information is missing, explicitly state that
the resume does not provide enough information.

If information is ambiguous, identify the ambiguity.

Do not infer skills, responsibilities, qualifications,
employment reasons, or experience that are not supported
by the document.
```

---

## Evaluation Prompt

Responsible for:

```text
Candidate Profile + Resume
          ↓
Hiring Evaluation
```

The model generates only the fields required by the corporate evaluation schema.

The output is subsequently validated using Pydantic.

---

# 10. Hallucination Prevention

The system uses multiple safeguards.

### 1. Source Restriction

The AI receives only:

```text
Uploaded Resume
+
Structured Candidate Profile
+
Recruiter's Question
```

for document-grounded Q&A.

---

### 2. Explicit Prompt Constraints

The prompts instruct the model not to invent candidate information.

---

### 3. Structured Output

AI-generated evaluations are mapped to predefined Pydantic models.

---

### 4. Validation

Invalid or malformed model output is rejected instead of being blindly used.

---

### 5. Missing Information Handling

When information is unavailable, the system uses explicit uncertainty instead of fabrication.

For example:

```text
The resume does not provide enough information
to determine which AWS services were used.
```

---

# 11. Deterministic Logic vs AI Logic

The system deliberately does not use AI for every operation.

## Deterministic application logic

Handled using Python:

* File parsing
* File validation
* Date calculations
* Employment gap calculations
* Schema validation
* PDF generation
* Dispatch simulation
* Error handling

## AI-powered logic

Handled by the LLM:

* Semantic information extraction
* Natural-language understanding
* Document-grounded Q&A
* Ambiguity identification
* Evaluation summarization
* Candidate information mapping

This separation improves reliability and makes the workflow easier to maintain.

---

# 12. Why RAG Is Not Used in the MVP

The current assessment focuses on processing an individual uploaded resume.

For a single candidate document, sending the extracted resume content as context is simpler and more reliable than introducing a vector database.

A full RAG pipeline would become useful when the system needs to handle:

* thousands of resumes
* multiple candidate documents
* long documents
* historical candidate records
* cross-document search

RAG is therefore documented as a future scalability enhancement rather than unnecessary infrastructure for this assessment MVP.

---

# 13. Technology Stack

### Frontend

* Streamlit

### Backend

* FastAPI
* Python

### AI

* OpenAI API

### Data Validation

* Pydantic

### Document Parsing

* PyMuPDF
* python-docx
* Python standard library

### Document Generation

* ReportLab

### Testing

* pytest

### Deployment

* Docker
* Render

### Source Control

* Git
* GitHub

---

# 14. Project Structure

```text
ai-recruiter-agent/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── prompts.py
│   ├── parser.py
│   ├── ai_service.py
│   ├── workflow.py
│   ├── document_service.py
│   └── email_service.py
│
├── frontend/
│   └── streamlit_app.py
│
├── data/
│   └── sample_resume.txt
│
├── generated/
│   └── .gitkeep
│
├── tests/
│   └── test_pipeline.py
│
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
└── LICENSE
```

The project intentionally avoids unnecessary layers and folders.

---

# 15. Environment Variables

Create a local `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your_available_model

HR_EMAIL=hr-admissions@company.mock

BACKEND_URL=http://localhost:8000
```

The `.env` file must never be committed to GitHub.

A safe template is provided in:

```text
.env.example
```

Example:

```env
OPENAI_API_KEY=
OPENAI_MODEL=

HR_EMAIL=hr-admissions@company.mock

BACKEND_URL=http://localhost:8000
```

---

# 16. Local Setup

## Prerequisites

Install:

* Python 3.11+
* Git
* Docker Desktop (optional)

---

## Clone the repository

```bash
git clone <repository-url>
cd ai-recruiter-agent
```

---

## Create virtual environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## Install dependencies

```bash
pip install -r requirements.txt
```

---

## Configure environment

Copy `.env.example` to `.env`.

Windows:

```bash
copy .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Add the OpenAI API key to `.env`.

---

# 17. Run the Backend

Start FastAPI:

```bash
uvicorn app.main:app --reload
```

The backend runs locally at:

```text
http://localhost:8000
```

Health check:

```text
GET /health
```

---

# 18. Run the Frontend

In a second terminal:

```bash
streamlit run frontend/streamlit_app.py
```

The Streamlit application will be available at the local address shown by Streamlit.

Make sure:

```env
BACKEND_URL=http://localhost:8000
```

is configured.

---

# 19. Docker

The project includes Docker configuration.

Build and run:

```bash
docker compose up --build
```

The application services are configured to communicate through environment-based configuration.

The application does not depend on machine-specific Windows paths.

---

# 20. API Endpoints

The MVP exposes only the endpoints required by the workflow.

| Method | Endpoint                              | Purpose                        |
| ------ | ------------------------------------- | ------------------------------ |
| GET    | `/health`                             | Backend health check           |
| POST   | `/api/resume/upload`                  | Upload and process resume      |
| POST   | `/api/ask`                            | Ask a question about candidate |
| POST   | `/api/evaluate`                       | Generate hiring evaluation     |
| POST   | `/api/dispatch`                       | Simulate HR dispatch           |
| GET    | `/api/evaluation/download/{filename}` | Download generated evaluation  |

---

# 21. Demo Workflow

The recommended demonstration flow is:

### Step 1 — Upload

Upload:

```text
data/sample_resume.txt
```

or a supported PDF/DOCX resume.

---

### Step 2 — Candidate Extraction

Review:

* Name
* Email
* Skills
* Education
* Experience
* Employment history
* Gaps
* Ambiguities

---

### Step 3 — Ask a Question

Example:

```text
Does this candidate have experience with cloud deployments,
and are there any unexplained employment gaps?
```

The AI provides a grounded response.

---

### Step 4 — Generate Evaluation

Click:

```text
Generate Evaluation
```

The agentic workflow executes automatically.

---

### Step 5 — Review Evaluation

The system generates the Corporate Hiring Evaluation.

---

### Step 6 — Download

Download the generated PDF.

---

### Step 7 — Dispatch

Click:

```text
Dispatch to HR
```

The system simulates sending the evaluation to:

```text
hr-admissions@company.mock
```

---

# 22. Error Handling

The application handles common failures including:

* Unsupported file formats
* Empty documents
* Unreadable documents
* Missing API keys
* OpenAI API errors
* Invalid AI responses
* Pydantic validation failures
* PDF generation failures
* Missing email configuration

User-facing errors are presented without exposing internal stack traces.

---

# 23. Security Considerations

The application follows basic security practices appropriate for the assessment MVP.

* API keys are stored in environment variables.
* `.env` is excluded from Git.
* Uploaded file types are validated.
* File names are sanitized.
* Uploaded content is not executed.
* Secrets are not exposed in the frontend.
* The demo uses fictional candidate data.
* Sensitive candidate information should not be committed to the repository.

A production deployment would require additional controls for personally identifiable information.

---

# 24. Deployment

The application is designed to be deployed using Render.

Recommended architecture:

```text
                  Internet
                     │
                     ▼
          ┌────────────────────┐
          │ Streamlit Service  │
          │     Frontend       │
          └─────────┬──────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ FastAPI Service    │
          │      Backend       │
          └─────────┬──────────┘
                    │
                    ▼
             ┌─────────────┐
             │ OpenAI API  │
             └─────────────┘
```

The Streamlit frontend and FastAPI backend can be deployed as separate Render services from the same GitHub repository.

The backend URL is configured through:

```env
BACKEND_URL=https://your-backend-url
```

The OpenAI API key is configured through Render environment variables and is never committed to source control.

---

# 25. Deployment Configuration

## Backend

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

```text
OPENAI_API_KEY
OPENAI_MODEL
HR_EMAIL
```

---

## Frontend

Start command:

```bash
streamlit run frontend/streamlit_app.py --server.address 0.0.0.0 --server.port $PORT
```

Required environment variable:

```text
BACKEND_URL=https://<deployed-backend-url>
```

---

# 26. Assessment Design Decisions

Several design decisions were made intentionally.

### Simple architecture

The application uses a small number of clearly separated components rather than unnecessary microservices.

### AI + deterministic logic

AI is used for language reasoning while Python handles predictable business logic.

### Structured outputs

Pydantic models prevent uncontrolled AI output from propagating through the application.

### Grounded Q&A

The recruiter assistant answers only from the supplied candidate information.

### Mock dispatch

Email dispatch is simulated because the assessment does not require a production email provider.

### Deployment readiness

The application uses environment variables and Docker-compatible configuration.

---

# 27. Limitations of the MVP

This implementation is intentionally scoped to the assessment.

Current limitations include:

* No authentication
* No persistent candidate database
* No OCR for scanned documents
* No large-scale document retrieval
* No ATS integration
* Mock email dispatch
* Single-document context
* Limited document formats
* No production-grade PII management

These limitations can be addressed in a production version.

---

# 28. Next Steps — If Another Week Were Available

## 1. OCR

Add OCR support for:

* scanned PDFs
* images
* photographed resumes

---

## 2. RAG

Introduce:

```text
Document
↓
Chunking
↓
Embeddings
↓
Vector Database
↓
Retriever
↓
LLM
```

This would allow the system to efficiently search large candidate document collections.

---

## 3. Candidate Database

Introduce PostgreSQL for persistent storage of:

* candidates
* resumes
* evaluations
* recruiter questions
* workflow history

---

## 4. ATS Integration

Integrate with applicant tracking systems so that evaluations can automatically update candidate records.

---

## 5. Real Email Integration

Replace the mock dispatch layer with a transactional email provider or SMTP service.

---

## 6. Human Approval

Add an approval checkpoint before final dispatch:

```text
AI Evaluation
      ↓
Recruiter Review
      ↓
Approve
      ↓
Dispatch
```

This would be especially useful for high-impact recruitment workflows.

---

## 7. Security & Privacy

Add:

* encryption
* authentication
* role-based access
* audit logs
* PII controls
* data retention policies
* secure document storage

---

## 8. Observability

Add:

* workflow tracing
* model usage tracking
* error monitoring
* latency monitoring
* AI response validation metrics

---

# 29. Testing

Run the test suite with:

```bash
pytest
```

The tests cover core application behavior including:

* document parsing
* invalid file handling
* candidate schema validation
* employment gap calculations
* evaluation validation
* dispatch simulation
* health endpoint

---

# 30. Final Acceptance Criteria

The application is considered complete when the following workflow works successfully:

```text
┌───────────────────────┐
│   Upload Resume       │
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│   Parse Document      │
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ AI Candidate          │
│ Extraction             │
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ Structured Profile    │
└───────────┬───────────┘
            │
       ┌────┴─────┐
       ▼          ▼
    Q&A       Evaluation
       │          │
       │          ▼
       │     Gap Analysis
       │          │
       │          ▼
       │     Form Generation
       │          │
       │          ▼
       │       PDF
       │          │
       │          ▼
       │       Dispatch
       │
       ▼
 Recruiter Answer
```

The complete system demonstrates:

**AI intelligence + document understanding + natural-language interaction + agentic workflow + automated business action.**

---

# 31. License

This project was created as part of a technical assessment.

The sample candidate information is fictional and intended only for demonstration purposes.
