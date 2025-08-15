from typing import List, Tuple
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from backend.paths import _doc_dir
from backend.state import DOC_CACHE
import json


def _chunks_path(doc_id: str):
    return _doc_dir(doc_id) / "chunks.json"


def save_chunks_json(doc_id: str, docs: List[Document]) -> None:
    data = [{"page_content": d.page_content, "metadata": d.metadata} for d in docs]
    _chunks_path(doc_id).write_text(json.dumps(data), encoding="utf-8")


def load_chunks_json(doc_id: str) -> List[Document] | None:
    p = _chunks_path(doc_id)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return [Document(page_content=it.get("page_content", ""), metadata=it.get("metadata", {})) for it in raw]
    except Exception:
        return None


def get_or_build_vectorstore_for_doc(doc_id: str, docs_builder: callable) -> Tuple[FAISS, List[Document]]:
    if doc_id in DOC_CACHE:
        cached = DOC_CACHE[doc_id]
        if "vectorstore" in cached and "docs" in cached:
            return cached["vectorstore"], cached["docs"]

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    folder = str(_doc_dir(doc_id))

    try:
        vs = FAISS.load_local(folder, embeddings, allow_dangerous_deserialization=True)
        docs = load_chunks_json(doc_id)
        if docs is None:
            docs = list(vs.docstore._dict.values())  # type: ignore[attr-defined]
        DOC_CACHE[doc_id] = {"vectorstore": vs, "docs": docs}
        return vs, docs
    except Exception:
        pass

    docs = docs_builder()
    vs = FAISS.from_documents(docs, embeddings)
    vs.save_local(folder)
    save_chunks_json(doc_id, docs)
    DOC_CACHE[doc_id] = {"vectorstore": vs, "docs": docs}
    return vs, docs


