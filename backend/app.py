
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from backend.lease_chain import (
    run_rag_pipeline,
    evaluate_general_risks,
    load_lease_docs,
    _compute_doc_id_for_file,
    _get_or_build_vectorstore_for_doc,
)
from backend.paths import _doc_dir
from backend.state import LATEST_DOC_ID as _LATEST_DOC_ID
from backend.config import get_allowed_origins, APP_VERSION
from backend.schemas import UploadResponse, AskResponse, AbnormalitiesResponse, ClausesResponse, ProjectCreate, ProjectOut, VersionCreate, LeaseVersionOut
from backend.db import session_scope
from backend.models import Base, Project, LeaseVersion, LeaseVersionStatus, RiskScore, AbnormalityRecord
from sqlalchemy import select
import json
from backend.storage import put_file
import shutil, os

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/test-cors")
def test_cors():
    return {"message": "CORS is working"}


# Projects
@app.post("/v1/projects", response_model=ProjectOut)
def create_project(body: ProjectCreate):
    with session_scope() as s:
        p = Project(name=body.name, description=body.description)
        s.add(p)
        s.flush()
        return ProjectOut(id=p.id, name=p.name, description=p.description)


@app.get("/v1/projects", response_model=list[ProjectOut])
def list_projects():
    with session_scope() as s:
        rows = s.execute(select(Project)).scalars().all()
        return [ProjectOut(id=r.id, name=r.name, description=r.description) for r in rows]


@app.post("/v1/projects/{project_id}/versions", response_model=LeaseVersionOut)
def create_version(project_id: str, body: VersionCreate):
    with session_scope() as s:
        v = LeaseVersion(project_id=project_id, label=body.label, status=LeaseVersionStatus.uploaded)
        s.add(v)
        s.flush()
        return LeaseVersionOut(id=v.id, project_id=v.project_id, label=v.label, status=v.status.value, created_at=v.created_at.isoformat() if v.created_at else None)


@app.post("/v1/projects/{project_id}/versions/upload", response_model=LeaseVersionOut)
async def upload_version_file(project_id: str, label: str | None = Form(default=None), file: UploadFile = File(...)):
    # Save raw PDF into storage
    os.makedirs("temp", exist_ok=True)
    tmp_path = f"temp/{file.filename or 'lease.pdf'}"
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    with session_scope() as s:
        v = LeaseVersion(project_id=project_id, label=label, status=LeaseVersionStatus.uploaded)
        s.add(v)
        s.flush()
        # Store file under storage/projects/{project_id}/{version_id}/lease.pdf
        rel = f"projects/{project_id}/{v.id}/lease.pdf"
        file_url = put_file(tmp_path, rel)
        v.file_url = file_url
        s.flush()
        return LeaseVersionOut(id=v.id, project_id=v.project_id, label=v.label, status=v.status.value, created_at=v.created_at.isoformat() if v.created_at else None)

@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    import os
    os.makedirs("temp", exist_ok=True)
    # Save to a temp path first
    tmp_path = "temp/lease.pdf"
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Compute doc_id and move to permanent location
    doc_id = _compute_doc_id_for_file(tmp_path)
    target_dir = _doc_dir(doc_id)
    target_path = str(target_dir / "lease.pdf")
    if not os.path.exists(target_path):
        shutil.copy(tmp_path, target_path)
    # Prebuild vector index so first query is instant
    _get_or_build_vectorstore_for_doc(doc_id)
    risks = evaluate_general_risks(target_path)
    # Persist risk analysis to DB (best effort)
    try:
        with session_scope() as s:
            # find or create a version for ad-hoc usage: fallback projectless
            v = s.execute(select(LeaseVersion).order_by(LeaseVersion.created_at.desc())).scalars().first()
            if v:
                rec = RiskScore(lease_version_id=v.id, payload=json.dumps(risks), model="gpt-4o")
                s.add(rec)
    except Exception:
        pass
    return {"message": "File uploaded successfully.", "doc_id": doc_id, "risks": risks}

@app.post("/ask", response_model=AskResponse)
async def ask_question(question: str = Form(...), doc_id: str | None = Form(default=None)):
    import os
    effective_doc_id = doc_id or _LATEST_DOC_ID
    if not effective_doc_id:
        return {"answer": "No document loaded yet. Please upload a PDF first."}
    pdf_path = str(_doc_dir(effective_doc_id) / "lease.pdf")
    if not os.path.exists(pdf_path):
        return {"answer": "Document not found on server. Please upload again."}
    answer = run_rag_pipeline(pdf_path, question)
    return {"answer": answer}
    
from fastapi import Body

from backend.lease_chain import get_clauses_for_topic, detect_abnormalities

@app.post("/abnormalities", response_model=AbnormalitiesResponse)
async def fetch_abnormalities(doc_id: str | None = Form(default=None)):
    import os
    effective_doc_id = doc_id or _LATEST_DOC_ID
    if not effective_doc_id:
        return {"abnormalities": ["No document loaded yet. Please upload a PDF first."]}
    pdf_path = str(_doc_dir(effective_doc_id) / "lease.pdf")
    if not os.path.exists(pdf_path):
        return {"abnormalities": ["Document not found on server. Please upload again."]}
    abnormalities = detect_abnormalities(pdf_path)
    try:
        with session_scope() as s:
            v = s.execute(select(LeaseVersion).order_by(LeaseVersion.created_at.desc())).scalars().first()
            if v:
                rec = AbnormalityRecord(lease_version_id=v.id, payload=json.dumps(abnormalities), model="gpt-4o")
                s.add(rec)
    except Exception:
        pass
    print(abnormalities)
    return {"abnormalities": abnormalities}

@app.post("/clauses", response_model=ClausesResponse)
async def fetch_clauses(topic: str = Form(...), doc_id: str | None = Form(default=None)):
    import os
    effective_doc_id = doc_id or _LATEST_DOC_ID
    if not effective_doc_id:
        return {"clauses": ["No document loaded yet. Please upload a PDF first."]}
    pdf_path = str(_doc_dir(effective_doc_id) / "lease.pdf")
    if not os.path.exists(pdf_path):
        return {"clauses": ["Document not found on server. Please upload again."]}
    print("Topic:\n", topic)
    clauses = get_clauses_for_topic(pdf_path, topic)
    print(clauses)
    return {"clauses": clauses}


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": APP_VERSION}

@app.get("/version")
def version():
    return {"version": APP_VERSION}
