
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from lease_chain import run_rag_pipeline, evaluate_general_risks, load_lease_docs
import shutil, os

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["lease-analyzer-7og7.vercel.app"],  # Change to your frontend URL later
    allow_credentials=True,
    allow_methods=["lease-analyzer-7og7.vercel.app"],
    allow_headers=["lease-analyzer-7og7.vercel.app"],
)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    import os
    os.makedirs("temp", exist_ok=True)
    with open("temp/lease.pdf", "wb") as f:
        shutil.copyfileobj(file.file, f)
    risks = evaluate_general_risks("temp/lease.pdf")
    return {"message": "File uploaded successfully.", "risks": risks}

@app.post("/ask")
async def ask_question(question: str = Form(...)):
    answer = run_rag_pipeline("temp/lease.pdf", question)
    return {"answer": answer}
    
from fastapi import Body

from lease_chain import get_clauses_for_topic

@app.post("/clauses")
async def fetch_clauses(topic: str = Form(...)):
    print("Topic:\n", topic)
    clauses = get_clauses_for_topic("temp/lease.pdf", topic)
    print(clauses)
    return {"clauses": clauses}
