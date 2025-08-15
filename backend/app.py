
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from backend.lease_chain import run_rag_pipeline, evaluate_general_risks, load_lease_docs, _get_or_build_vectorstore_for_doc, _doc_dir, _compute_doc_id_for_file, _LATEST_DOC_ID
from backend.config import get_allowed_origins, APP_VERSION
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

@app.post("/upload")
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
    return {"message": "File uploaded successfully.", "doc_id": doc_id, "risks": risks}

@app.post("/ask")
async def ask_question(question: str = Form(...), doc_id: str | None = Form(default=None)):
    import os
    from backend.lease_chain import _LATEST_DOC_ID, _doc_dir
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

@app.post("/abnormalities")
async def fetch_abnormalities(doc_id: str | None = Form(default=None)):
    import os
    from backend.lease_chain import _LATEST_DOC_ID, _doc_dir
    effective_doc_id = doc_id or _LATEST_DOC_ID
    if not effective_doc_id:
        return {"abnormalities": ["No document loaded yet. Please upload a PDF first."]}
    pdf_path = str(_doc_dir(effective_doc_id) / "lease.pdf")
    if not os.path.exists(pdf_path):
        return {"abnormalities": ["Document not found on server. Please upload again."]}
    abnormalities = detect_abnormalities(pdf_path)
    print(abnormalities)
    return {"abnormalities": abnormalities}

@app.post("/clauses")
async def fetch_clauses(topic: str = Form(...), doc_id: str | None = Form(default=None)):
    import os
    from backend.lease_chain import _LATEST_DOC_ID, _doc_dir
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
