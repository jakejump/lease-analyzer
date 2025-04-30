from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.schema import Document
from typing import List
import re
import json


def extract_text_from_pdf(pdf_path: str) -> str:
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    print("docs", docs)
    return "\n".join(doc.page_content for doc in docs)


def split_into_paragraphs_or_clauses(text: str) -> List[str]:
    clause_pattern = re.compile(
        r"(\n|^)(Section|Clause|Article)?\s*(\d{1,2}(\.\d{1,2})?)[\.:\)\-\s]+.*?(?=\n(Section|Clause|Article)?\s*\d{1,2}(\.\d{1,2})?[\.:\)\-\s]+|\Z)",
        re.DOTALL | re.IGNORECASE
    )

    # Find all clause-like matches
    matches = list(clause_pattern.finditer(text))
    clauses = []
    seen_numbers = set()

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        clause_text = text[start:end].strip()

        # Extract clause number (e.g., 1, 1.1, 2)
        clause_number_match = re.search(r"(\d{1,2}(\.\d{1,2})?)", match.group())
        if clause_number_match:
            clause_number = clause_number_match.group(1)
            # Skip if out of order or already seen
            if clause_number in seen_numbers:
                continue
            seen_numbers.add(clause_number)
            clauses.append(clause_text)

    # Fallback if pattern fails or results are too few/many
    total_chars = len(text)
    if len(clauses) < 7 or len(clauses) > max(100, total_chars // 200):
        print("⚠️ Smart clause split failed, using paragraph fallback.")
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > 40]
        return paragraphs
        
    print("clauses: ", clauses)

    return clauses


def load_lease_docs(pdf_path: str) -> List[Document]:
    loader = UnstructuredPDFLoader(pdf_path, mode="elements")
    print("text", text)
    paragraphs = split_into_paragraphs_or_clauses(text)
    return [Document(page_content=para, metadata={"index": i}) for i, para in enumerate(paragraphs)]


def run_rag_pipeline(pdf_path, question):
    chunks = load_lease_docs(pdf_path)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 6})

    SYSTEM = """
    You are a contract analyst reviewing a commercial lease agreement. Based on the provided context,
    answer the user's question. Return your answer in plain English.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM.strip()),
        ("human", "Context:\n{context}\n\nQuestion: {question}")
    ])

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain.invoke(question)


def evaluate_general_risks(pdf_path):
    chunks = load_lease_docs(pdf_path)
    print("chunks", chunks)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 12})

    SYSTEM = """
    You are a risk analyst evaluating a lease document. You are an analyst for a firm that is purchasing or puttng together commercial real-estate deals, so the risk should be from the perspective of the lessor. Based on the following context, score the lease across the following general risk categories from 1 (high risk) to 10 (low risk) and explain each score:

    - Cash Flow Adjustments:
        Lease Structure (Who Pays What?)
            Gross Lease: Landlord pays most or all property expenses (riskier for landlord).
            Net Lease: Tenant pays some or all operating expenses.
                Single Net: Tenant pays property taxes.
                Double Net: Taxes + insurance.
                Triple Net (NNN): Taxes + insurance + maintenance.
            Risk: Gross leases shift cost risk to you; NNN leases shift it to tenants (safer).
        Capital Expenditure (CapEx) Obligations
            Who is responsible for big repairs like roof, HVAC, structure?
            Tenant Improvement (TI) Allowances: Did the landlord promise money for upgrades?
            Risk: You could be on the hook for big unexpected costs.
        Co-tenancy clauses (in retail leases: tenant can pay less or leave if anchor tenants leave).
        Free rent periods or concessions built into the lease.
        
    - Future Cash Flow:
        Renewal options (does tenant have options to stay longer, and at what rates?)
        Risk: Short-term leases = turnover risk, renewal uncertainty.
        Scheduled rent escalations (fixed bumps? CPI-linked increases?)
        Risk: If market rents are falling, or if you're locked into below-market leases, it hurts cash flow and future value.
        Outline exposure to inflation and changes in interest rates

    - Inflation/Interest Rate Exposure:
	    Macro implications of the lease contract. 
        If there is high inflation, how do rent escalations hold up, how do renewal options affect the value of the lease contract, how does the specific working of cash flow adjustments (like TI and lease structure) hold up. 
        Is it beneficial for the lessor or is it a negative.
        Apply the same logic to changes in global/nationwide interest rates.

    - Use and Exclusivity Clauses:
        Permitted use: What exactly can the tenant do on the property?
        Exclusive use rights: Do they have rights that could restrict future tenants?
        Risk: Restrictions can limit re-leasing flexibility.
        Sublease or assignment rights (can tenant sublease easily? Risk of poor subtenants.)
        SNDA agreements (Subordination, Non-Disturbance, and Attornment).

    - Default and Termination Clauses:
        Early termination rights (can the tenant break the lease? On what terms?)
        Default provisions (what triggers an eviction? Cure periods?)
        Risk: Easy outs or weak default clauses mean unstable cash flow.

    - Collateral and Insurance:
        Security Deposits, Guarantees, and Collateral
            Security deposit size and conditions.
            Personal or corporate guarantees (especially important for smaller tenants).
            Letters of credit or other forms of collateral.
            Risk: More security = better recovery in a default.
        Insurance Requirements
            Tenant’s insurance obligations (and evidence they maintain them).
            Landlord's insurance coverage (especially for common areas).
            Risk: Poor insurance setups = risk of uncovered losses.

    Please return your result strictly in the following JSON format, and nothing else:

    {{
      "cash _flow_adjustments": {{"score": int, "explanation": str}},
      "future_cash_flow": {{"score": int, "explanation": str}},
      "inflation/interest_rate_exposure": {{"score": int, "explanation": str}},
      "use_and_exclusivity_clauses": {{"score": int, "explanation": str}},
      "default_and_termination_clauses": {{"score": int, "explanation": str}},
      "collateral_and_insurance": {{"score": int, "explanation": str}}
    }}

    Do not include any commentary or markdown — only valid JSON.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM.strip()),
        ("human", "Context:\n{context}\n\nEvaluate the lease risks.")
    ])

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    raw_output = chain.invoke("Evaluate the lease risks.")

    try:
        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").removesuffix("```")
        result = json.loads(cleaned)
        assert isinstance(result, dict)
        print("risks", result)
        return result
    except Exception as e:
        print("⚠️ LLM returned invalid JSON:\n", raw_output)
        return {
            "termination_risk": {"score": None, "explanation": "Could not parse response."},
            "financial_exposure": {"score": None, "explanation": "Could not parse response."},
            "legal_ambiguity": {"score": None, "explanation": "Could not parse response."},
            "operational_complexity": {"score": None, "explanation": "Could not parse response."},
            "assignment_subletting_risk": {"score": None, "explanation": "Could not parse response."},
            "renewal_escalation_risk": {"score": None, "explanation": "Could not parse response."}
        }
        
def detect_abnormalities(pdf_path):
    chunks = load_lease_docs(pdf_path)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 12})

    SYSTEM = """
    You are an expert lease reviewer. Identify any unusual, uncommon, or non-standard clauses in this lease.
    These may include non-standard financial penalties, strange renewal conditions, unexpected maintenance responsibilities, etc.
    Only return items that deviate from common practice. If everything is normal, say: "No abnormalities found."

    Return the output as a list of strings in JSON format, e.g.:
    [
      "Clause 7 requires the tenant to cover 100% of HVAC replacement costs, which is unusual.",
      "Clause 12 allows the landlord to raise rent without notice during renewal, which is non-standard."
    ]
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM.strip()),
        ("human", "Context:\n{context}\n\nIdentify abnormalities.")
    ])

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    result = chain.invoke("Identify abnormalities in the lease.")
    print(result)
    try:
        return json.loads(result)
    except Exception as e:
        return ["Could not parse LLM response."]


def get_clauses_for_topic(pdf_path, topic):
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    chunks = load_lease_docs(pdf_path)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_documents(chunks, embeddings)

    topic_embedding = embeddings.embed_query(topic)
    stored_embeddings = vectorstore.index.reconstruct_n(0, vectorstore.index.ntotal)
    stored_docs = vectorstore.docstore._dict.values()

    similarities = cosine_similarity([topic_embedding], stored_embeddings)[0]
    doc_scores = list(zip(stored_docs, similarities))

    threshold = 0.65
    filtered = [(doc, score) for doc, score in doc_scores if score >= threshold]
    if not filtered:
        filtered = sorted(doc_scores, key=lambda x: x[1], reverse=True)[:3]

    return [doc.page_content.strip() for doc, _ in filtered]
