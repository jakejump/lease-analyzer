from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _temp_root() -> Path:
    temp_dir = _project_root() / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _doc_dir(doc_id: str) -> Path:
    directory = _temp_root() / doc_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def doc_id_from_pdf_path(pdf_path: str | Path) -> str:
    return Path(pdf_path).resolve().parent.name


