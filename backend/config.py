import os
from typing import List


APP_VERSION = os.getenv("APP_VERSION", "0.1.0")


def get_allowed_origins() -> List[str]:
    # Comma-separated env var; fallback to common local URLs and prod preview
    raw = os.getenv("ALLOWED_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://lease-analyzer-7og7.vercel.app",
    ]


