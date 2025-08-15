from typing import List, Dict, Tuple
import re
from difflib import SequenceMatcher

from backend.lease_chain import extract_text_from_pdf
from backend.clauses import split_into_clauses


def _parse_clause_number_and_body(clause_text: str) -> Tuple[str | None, str]:
    text = clause_text.strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    header_line = lines[0] if lines else ""
    m = re.match(r"^(?:Section|Clause|Article)?\s*(\d{1,2}(?:\.\d{1,2})?)\b[\s\-:\.)]*", header_line, re.IGNORECASE)
    number = m.group(1) if m else None
    body = "\n".join(lines[1:]) if len(lines) > 1 else ("\n".join(lines) if lines else "")
    body = " ".join(body.split())
    return number, body


def _index_by_number(clauses: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for c in clauses:
        num, body = _parse_clause_number_and_body(c)
        if num:
            out[num] = body
    return out


def _modified(a: str, b: str, threshold: float = 0.9) -> bool:
    # Simple similarity on normalized strings
    a_n = " ".join(a.split())
    b_n = " ".join(b.split())
    ratio = SequenceMatcher(None, a_n, b_n).ratio()
    return ratio < threshold


def diff_pdfs(base_pdf_path: str, compare_pdf_path: str) -> List[Dict]:
    base_text = extract_text_from_pdf(base_pdf_path)
    compare_text = extract_text_from_pdf(compare_pdf_path)

    base_clauses = split_into_clauses(base_text)
    compare_clauses = split_into_clauses(compare_text)

    base_idx = _index_by_number(base_clauses)
    compare_idx = _index_by_number(compare_clauses)

    changes: List[Dict] = []

    # Removed or modified
    for num, before in base_idx.items():
        if num not in compare_idx:
            changes.append({"type": "removed", "clause_no": num, "before": before, "after": None})
        else:
            after = compare_idx[num]
            if _modified(before, after):
                changes.append({"type": "modified", "clause_no": num, "before": before, "after": after})

    # Added
    for num, after in compare_idx.items():
        if num not in base_idx:
            changes.append({"type": "added", "clause_no": num, "before": None, "after": after})

    return changes


