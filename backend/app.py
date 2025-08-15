
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from backend.lease_chain import run_rag_pipeline, evaluate_general_risks, load_lease_docs
import shutil, os

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://lease-analyzer-7og7.vercel.app",
    ],
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
    from backend.lease_chain import _compute_doc_id_for_file, _doc_dir
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
