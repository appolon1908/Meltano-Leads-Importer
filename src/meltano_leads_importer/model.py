from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Mapping

def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def canonical_json(row: Mapping[str, object]) -> str:
    return json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def source_fingerprint(row: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(row).encode("utf-8")).hexdigest()

def first_present(row: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""

def raw_projection(row: Mapping[str, object]) -> tuple[str | None, str | None]:
    country = first_present(row, "country") or None
    category = first_present(row, "business_category", "lead_category") or None
    return country, category
