# Multi-purpose Python Dockerfile for AI Recruiter Agent (FastAPI Backend / Streamlit Frontend)
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if required for PDF/document processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create generated artifacts directory
RUN mkdir -p /app/generated /app/data

# Default expose ports (FastAPI: 8000, Streamlit: 8501)
EXPOSE 8000 8501

# Default command launches FastAPI backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
