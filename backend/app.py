
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
from backend.schemas import UploadResponse, AskResponse, AbnormalitiesResponse, ClausesResponse, ProjectCreate, ProjectOut, VersionCreate, LeaseVersionOut, VersionStatusResponse, RiskOut, AbnormalitiesOut
from backend.db import session_scope
from backend.models import Base, Project, LeaseVersion, LeaseVersionStatus, RiskScore, AbnormalityRecord
from sqlalchemy import select
import json
from backend.storage import put_file
from backend.jobs import get_queue, process_version
from redis import Redis
from backend.db import engine
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


@app.on_event("startup")
def on_startup() -> None:
    # Auto-create tables in dev; in prod use Alembic migrations
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass


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


@app.get("/v1/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str):
    with session_scope() as s:
        p = s.get(Project, project_id)
        if not p:
            return {"id": project_id, "name": "", "description": None}
        return ProjectOut(id=p.id, name=p.name, description=p.description)


@app.post("/v1/projects/{project_id}/versions", response_model=LeaseVersionOut)
def create_version(project_id: str, body: VersionCreate):
    with session_scope() as s:
        v = LeaseVersion(project_id=project_id, label=body.label, status=LeaseVersionStatus.uploaded)
        s.add(v)
        s.flush()
        return LeaseVersionOut(id=v.id, project_id=v.project_id, label=v.label, status=v.status.value, created_at=v.created_at.isoformat() if v.created_at else None)


@app.get("/v1/projects/{project_id}/versions", response_model=list[LeaseVersionOut])
def list_versions(project_id: str):
    with session_scope() as s:
        rows = s.query(LeaseVersion).filter(LeaseVersion.project_id == project_id).order_by(LeaseVersion.created_at.desc()).all()
        return [
            LeaseVersionOut(
                id=r.id,
                project_id=r.project_id,
                label=r.label,
                status=r.status.value,
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
            for r in rows
        ]


@app.post("/v1/projects/{project_id}/versions/upload", response_model=LeaseVersionOut)
async def upload_version_file(project_id: str, label: str | None = Form(default=None), file: UploadFile = File(...)):
    # Save raw PDF into storage
    os.makedirs("temp", exist_ok=True)
    tmp_path = f"temp/{file.filename or 'lease.pdf'}"
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Compute content hash for dedupe
    import hashlib
    with open(tmp_path, "rb") as f:
        content = f.read()
    content_hash = hashlib.md5(content).hexdigest()
    with session_scope() as s:
        existing = s.query(LeaseVersion).filter(LeaseVersion.content_hash == content_hash, LeaseVersion.doc_id.isnot(None)).order_by(LeaseVersion.created_at.desc()).first()
        v = LeaseVersion(project_id=project_id, label=label, status=LeaseVersionStatus.uploaded, content_hash=content_hash)
        s.add(v)
        s.flush()
        # Store file under storage/projects/{project_id}/{version_id}/lease.pdf
        rel = f"projects/{project_id}/{v.id}/lease.pdf"
        file_url = put_file(tmp_path, rel)
        v.file_url = file_url
        if existing and existing.doc_id:
            v.doc_id = existing.doc_id
            v.status = LeaseVersionStatus.processed
            try:
                # clone most recent analyses
                rec = s.query(RiskScore).filter(RiskScore.lease_version_id == existing.id).order_by(RiskScore.created_at.desc()).first()
                if rec:
                    s.add(RiskScore(lease_version_id=v.id, payload=rec.payload, model=rec.model))
                ab = s.query(AbnormalityRecord).filter(AbnormalityRecord.lease_version_id == existing.id).order_by(AbnormalityRecord.created_at.desc()).first()
                if ab:
                    s.add(AbnormalityRecord(lease_version_id=v.id, payload=ab.payload, model=ab.model))
            except Exception:
                pass
        else:
            # Enqueue background processing
            try:
                q = get_queue()
                q.enqueue(process_version, v.id)
            except Exception:
                pass
        s.flush()
        return LeaseVersionOut(id=v.id, project_id=v.project_id, label=v.label, status=v.status.value, created_at=v.created_at.isoformat() if v.created_at else None)


@app.get("/v1/versions/{version_id}/status", response_model=VersionStatusResponse)
def get_version_status(version_id: str):
    with session_scope() as s:
        v = s.get(LeaseVersion, version_id)
        if not v:
            return {"id": version_id, "status": "not_found"}
        stage = None
        progress = None
        try:
            conn = Redis()
            data = conn.hgetall(f"version:{version_id}:status")
            if data:
                stage = (data.get(b"stage") or b"").decode() or None
                val = (data.get(b"progress") or b"").decode()
                progress = int(val) if val.isdigit() else None
        except Exception:
            pass
        return VersionStatusResponse(
            id=v.id,
            status=v.status.value,
            created_at=v.created_at.isoformat() if v.created_at else None,
            updated_at=v.updated_at.isoformat() if v.updated_at else None,
            stage=stage,
            progress=progress,
        )


@app.get("/v1/versions/{version_id}/risk", response_model=RiskOut)
def get_version_risk(version_id: str):
    with session_scope() as s:
        rec = s.query(RiskScore).filter(RiskScore.lease_version_id == version_id).order_by(RiskScore.created_at.desc()).first()
        if not rec:
            return RiskOut(payload={})
        return RiskOut(payload=json.loads(rec.payload), model=rec.model, created_at=rec.created_at.isoformat() if rec.created_at else None)


@app.get("/v1/versions/{version_id}/abnormalities", response_model=AbnormalitiesOut)
def get_version_abnormalities(version_id: str):
    with session_scope() as s:
        rec = s.query(AbnormalityRecord).filter(AbnormalityRecord.lease_version_id == version_id).order_by(AbnormalityRecord.created_at.desc()).first()
        if not rec:
            return AbnormalitiesOut(payload=[])
        return AbnormalitiesOut(payload=json.loads(rec.payload), model=rec.model, created_at=rec.created_at.isoformat() if rec.created_at else None)


@app.post("/v1/versions/{version_id}/ask", response_model=AskResponse)
def ask_version(version_id: str, question: str = Form(...)):
    with session_scope() as s:
        v = s.get(LeaseVersion, version_id)
        if not v or not v.doc_id:
            return {"answer": "Version not processed yet."}
        pdf_path = str(_doc_dir(v.doc_id) / "lease.pdf")
        ans = run_rag_pipeline(pdf_path, question)
        return AskResponse(answer=ans)


@app.post("/v1/versions/{version_id}/clauses", response_model=ClausesResponse)
def clauses_version(version_id: str, topic: str = Form(...)):
    with session_scope() as s:
        v = s.get(LeaseVersion, version_id)
        if not v or not v.doc_id:
            return {"clauses": []}
        pdf_path = str(_doc_dir(v.doc_id) / "lease.pdf")
        from backend.lease_chain import get_clauses_for_topic
        res = get_clauses_for_topic(pdf_path, topic)
        return ClausesResponse(clauses=res)

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
