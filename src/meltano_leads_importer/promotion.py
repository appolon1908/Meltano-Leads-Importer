from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping

from .model import first_present
from .store import record_promotion, rows_for_promotion

def map_to_leads_api(row: Mapping[str, Any]) -> dict[str, Any]:
    contact_name = first_present(row, "full_name", "contact_name")
    if not contact_name:
        contact_name = " ".join(
            v for v in (
                first_present(row, "first_name"),
                first_present(row, "middle_name"),
                first_present(row, "last_name"),
            ) if v
        )
    business_name = first_present(row, "company", "business_name") or contact_name or "(unknown)"
    return {
        "lead_id": first_present(row, "lead_id") or None,
        "business_name": business_name,
        "contact_name": contact_name or None,
        "country": first_present(row, "country") or "Unknown",
        "business_category": first_present(row, "business_category", "lead_category") or "Uncategorized",
        "email": first_present(row, "email", "email_primary") or None,
        "phone": first_present(row, "phone", "mobile", "direct_phone", "company_phone") or None,
        "website": first_present(row, "website") or None,
        "status": first_present(row, "status", "verification_status") or "New",
        "notes": first_present(row, "notes") or None,
        "campaign_source": first_present(row, "source", "campaign_source") or None,
        "verification_status": first_present(row, "verification_status") or None,
        "verification_score": first_present(row, "verification_score") or 0,
        "data_quality_status": first_present(row, "data_quality_status") or None,
    }

def _request_json(url: str, method: str = "GET", payload: Mapping[str, Any] | None = None, timeout: int = 15):
    data = None if payload is None else json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            value = json.loads(body) if body else {}
        except json.JSONDecodeError:
            value = {"detail": body}
        return exc.code, value

def check_workstation(base_url: str) -> dict[str, Any]:
    code, body = _request_json(base_url.rstrip("/") + "/health")
    return {"ok": code == 200 and bool(body.get("ok")), "status_code": code, "body": body}

def promote_batch(db_path: str, batch_id: str, base_url: str, limit: int | None = None) -> dict[str, int]:
    counters = {"attempted": 0, "promoted": 0, "duplicate": 0, "review": 0, "failed": 0}
    for raw in rows_for_promotion(db_path, batch_id, limit):
        counters["attempted"] += 1
        source = json.loads(raw["payload_json"])
        payload = {k: v for k, v in map_to_leads_api(source).items() if v is not None}
        try:
            code, body = _request_json(base_url.rstrip("/") + "/api/leads", "POST", payload)
            if code in {200, 201}:
                status = "promoted"
            elif code == 409:
                status = "duplicate"
            elif code == 400:
                status = "review"
            else:
                status = "failed"
        except Exception as exc:
            status = "failed"
            body = {"error": repr(exc)}
        record_promotion(db_path, raw["raw_id"], status, body)
        counters[status] += 1
    return counters
