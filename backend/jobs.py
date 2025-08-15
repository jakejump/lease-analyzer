import json
from rq import Queue
from redis import Redis
from typing import Optional

from backend.models import LeaseVersion, LeaseVersionStatus, RiskScore, AbnormalityRecord
from backend.db import session_scope
from backend.paths import _doc_dir
from backend.lease_chain import evaluate_general_risks, detect_abnormalities, _get_or_build_vectorstore_for_doc


def get_queue() -> Queue:
    redis_url = None  # default localhost
    conn = Redis.from_url(redis_url) if redis_url else Redis()
    return Queue("default", connection=conn)


def process_version(version_id: str) -> None:
    """Run extraction/indexing/analyses for a lease version (simplified synchronous pipeline)."""
    with session_scope() as s:
        v: Optional[LeaseVersion] = s.get(LeaseVersion, version_id)
        if not v or not v.file_url:
            return
        # Copy file to expected working path if needed
        # For now assume v.file_url is accessible; put it under temp/{version_id}/lease.pdf for current pipeline
        # Build vectorstore
        try:
            # Map to doc_id = version_id
            import os, shutil
            os.makedirs("temp", exist_ok=True)
            temp_pdf = f"temp/{version_id}.pdf"
            if v.file_url and os.path.exists(v.file_url):
                shutil.copy(v.file_url, temp_pdf)
            from backend.lease_chain import _compute_doc_id_for_file, _doc_dir
            doc_id = _compute_doc_id_for_file(temp_pdf)
            target_dir = _doc_dir(doc_id)
            target_pdf = str(target_dir / "lease.pdf")
            if not os.path.exists(target_pdf):
                shutil.copy(temp_pdf, target_pdf)
            _get_or_build_vectorstore_for_doc(doc_id)

            # Analyses
            risks = evaluate_general_risks(target_pdf)
            abn = detect_abnormalities(target_pdf)
            s.add(RiskScore(lease_version_id=version_id, payload=json.dumps(risks), model="gpt-4o"))
            s.add(AbnormalityRecord(lease_version_id=version_id, payload=json.dumps(abn), model="gpt-4o"))
            v.status = LeaseVersionStatus.processed
        except Exception:
            v.status = LeaseVersionStatus.failed
        s.flush()


