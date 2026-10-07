from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from .model import canonical_json, now_utc, raw_projection, source_fingerprint

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS import_batches (
    import_batch_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_format TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    rows_seen INTEGER NOT NULL DEFAULT 0,
    rows_inserted INTEGER NOT NULL DEFAULT 0,
    rows_skipped INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS lead_import_raw (
    raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_batch_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    ingested_at TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    country_raw TEXT,
    business_category_raw TEXT,
    payload_json TEXT NOT NULL,
    promotion_status TEXT NOT NULL DEFAULT 'staged',
    promotion_result TEXT,
    UNIQUE(import_batch_id, source_fingerprint),
    FOREIGN KEY(import_batch_id) REFERENCES import_batches(import_batch_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_batch ON lead_import_raw(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_raw_status ON lead_import_raw(promotion_status);
CREATE INDEX IF NOT EXISTS idx_raw_country ON lead_import_raw(country_raw);
CREATE INDEX IF NOT EXISTS idx_raw_category ON lead_import_raw(business_category_raw);
"""

def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def connect(db_path: str | Path) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

@contextmanager
def db_connection(db_path: str | Path):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: str | Path) -> None:
    with db_connection(db_path) as conn:
        conn.executescript(DDL)

def iter_rows(path: str | Path) -> Iterator[tuple[int, dict[str, Any]]]:
    src = Path(path)
    suffix = src.suffix.lower()
    if suffix == ".csv":
        with src.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                raise ValueError("CSV has no header")
            for idx, row in enumerate(reader, start=2):
                yield idx, dict(row)
        return
    if suffix in {".jsonl", ".ndjson"}:
        with src.open("r", encoding="utf-8-sig") as fh:
            for idx, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"line {idx} is not a JSON object")
                yield idx, value
        return
    if suffix == ".json":
        value = json.loads(src.read_text(encoding="utf-8-sig"))
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            raise ValueError("JSON source must be an object or list of objects")
        for idx, row in enumerate(value, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"item {idx} is not a JSON object")
            yield idx, row
        return
    raise ValueError(f"unsupported source format: {suffix}")

def preview(path: str | Path, limit: int = 5) -> dict[str, Any]:
    src = Path(path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    samples = []
    seen = 0
    country_present = 0
    category_present = 0
    fingerprints = set()
    duplicate_rows = 0
    for row_no, row in iter_rows(src):
        seen += 1
        country, category = raw_projection(row)
        country_present += bool(country)
        category_present += bool(category)
        fp = source_fingerprint(row)
        if fp in fingerprints:
            duplicate_rows += 1
        else:
            fingerprints.add(fp)
        if len(samples) < max(0, limit):
            samples.append({"source_row": row_no, "fingerprint": fp, "row": row})
    return {
        "source_path": str(src),
        "source_name": src.name,
        "source_sha256": sha256_file(src),
        "source_format": src.suffix.lower().lstrip("."),
        "rows_seen": seen,
        "unique_row_fingerprints": len(fingerprints),
        "duplicate_row_instances": duplicate_rows,
        "rows_with_country": country_present,
        "rows_with_business_category": category_present,
        "samples": samples,
    }

def import_source(db_path: str | Path, source_path: str | Path, batch_id: str | None = None) -> dict[str, Any]:
    init_db(db_path)
    src = Path(source_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    source_hash = sha256_file(src)
    batch_id = batch_id or f"{src.stem}-{source_hash[:12]}"
    source_format = src.suffix.lower().lstrip(".")
    started = now_utc()

    with db_connection(db_path) as conn:
        prior = conn.execute("SELECT * FROM import_batches WHERE import_batch_id=?", (batch_id,)).fetchone()
        if prior and prior["status"] == "completed":
            return dict(prior)
        conn.execute(
            """
            INSERT INTO import_batches(
              import_batch_id,source_name,source_path,source_sha256,source_format,started_at,status
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(import_batch_id) DO UPDATE SET
              source_name=excluded.source_name,
              source_path=excluded.source_path,
              source_sha256=excluded.source_sha256,
              source_format=excluded.source_format,
              started_at=excluded.started_at,
              status='running',
              error=NULL
            """,
            (batch_id, src.name, str(src), source_hash, source_format, started, "running"),
        )
        seen = inserted = skipped = 0
        try:
            for row_no, row in iter_rows(src):
                seen += 1
                fp = source_fingerprint(row)
                country, category = raw_projection(row)
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO lead_import_raw(
                      import_batch_id,source_name,source_path,source_row,ingested_at,
                      source_fingerprint,country_raw,business_category_raw,payload_json
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        batch_id, src.name, str(src), row_no, now_utc(), fp,
                        country, category, canonical_json(row),
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    skipped += 1
                if seen % 5000 == 0:
                    conn.commit()
            conn.execute(
                """
                UPDATE import_batches SET completed_at=?,rows_seen=?,rows_inserted=?,
                rows_skipped=?,status='completed' WHERE import_batch_id=?
                """,
                (now_utc(), seen, inserted, skipped, batch_id),
            )
            conn.commit()
        except Exception as exc:
            conn.execute(
                """
                UPDATE import_batches SET completed_at=?,rows_seen=?,rows_inserted=?,
                rows_skipped=?,status='failed',error=? WHERE import_batch_id=?
                """,
                (now_utc(), seen, inserted, skipped, repr(exc), batch_id),
            )
            conn.commit()
            raise
        return dict(conn.execute("SELECT * FROM import_batches WHERE import_batch_id=?", (batch_id,)).fetchone())

def stats(db_path: str | Path) -> dict[str, Any]:
    init_db(db_path)
    with db_connection(db_path) as conn:
        return {
            "raw_rows": conn.execute("SELECT COUNT(*) FROM lead_import_raw").fetchone()[0],
            "staged": conn.execute("SELECT COUNT(*) FROM lead_import_raw WHERE promotion_status='staged'").fetchone()[0],
            "promoted": conn.execute("SELECT COUNT(*) FROM lead_import_raw WHERE promotion_status='promoted'").fetchone()[0],
            "duplicates": conn.execute("SELECT COUNT(*) FROM lead_import_raw WHERE promotion_status='duplicate'").fetchone()[0],
            "review": conn.execute("SELECT COUNT(*) FROM lead_import_raw WHERE promotion_status='review'").fetchone()[0],
            "batches": [dict(r) for r in conn.execute("SELECT * FROM import_batches ORDER BY started_at DESC LIMIT 20")],
        }

def rows_for_promotion(db_path: str | Path, batch_id: str, limit: int | None = None):
    init_db(db_path)
    sql = """
      SELECT raw_id,payload_json FROM lead_import_raw
      WHERE import_batch_id=? AND promotion_status='staged'
      ORDER BY raw_id
    """
    params: list[Any] = [batch_id]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(max(1, int(limit)))
    with db_connection(db_path) as conn:
        return [dict(r) for r in conn.execute(sql, params)]

def record_promotion(db_path: str | Path, raw_id: int, status: str, result: Mapping[str, Any]) -> None:
    if status not in {"promoted", "duplicate", "review", "failed"}:
        raise ValueError(status)
    with db_connection(db_path) as conn:
        conn.execute(
            "UPDATE lead_import_raw SET promotion_status=?,promotion_result=? WHERE raw_id=?",
            (status, json.dumps(dict(result), ensure_ascii=False, separators=(",", ":")), raw_id),
        )
