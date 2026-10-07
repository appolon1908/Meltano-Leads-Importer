#!/usr/bin/env python3
"""Prepare a frozen source CSV for governed raw staging.

The source file is never modified. The derived CSV appends the provenance fields
required by contracts/import-contract.v1.json so tap-csv can load it only into
lead_import_raw. No canonical lead writes occur here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

METADATA_COLUMNS = (
    "import_batch_id",
    "source_name",
    "source_row",
    "ingested_at",
    "source_fingerprint",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_fingerprint(row: dict[str, str]) -> str:
    canonical = json.dumps(
        row,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def normalize_timestamp(value: str | None) -> str:
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("--ingested-at must include a timezone")
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def prepare(
    source: Path,
    output: Path,
    *,
    batch_id: str,
    source_name: str,
    ingested_at: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    if not source.is_file():
        raise FileNotFoundError(source)
    UUID(batch_id)
    if not source_name.strip():
        raise ValueError("source_name must not be blank")

    source_sha = sha256_file(source)
    if expected_sha256 and source_sha.lower() != expected_sha256.lower():
        raise ValueError(
            f"source SHA-256 mismatch: expected {expected_sha256.lower()} got {source_sha}"
        )

    ts = normalize_timestamp(ingested_at)
    output.parent.mkdir(parents=True, exist_ok=True)

    row_count = 0
    with source.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        fields = reader.fieldnames or []
        if not fields:
            raise ValueError("source CSV has no header")
        collisions = sorted(set(fields).intersection(METADATA_COLUMNS))
        if collisions:
            raise ValueError("source already contains metadata columns: " + ", ".join(collisions))

        fd, tmp_name = tempfile.mkstemp(
            prefix=output.name + ".", suffix=".tmp", dir=str(output.parent)
        )
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            with tmp.open("w", encoding="utf-8", newline="") as dst:
                writer = csv.DictWriter(dst, fieldnames=[*fields, *METADATA_COLUMNS])
                writer.writeheader()
                for source_row, row in enumerate(reader, start=2):
                    original = {key: (row.get(key) or "") for key in fields}
                    writer.writerow(
                        {
                            **original,
                            "import_batch_id": batch_id,
                            "source_name": source_name,
                            "source_row": source_row,
                            "ingested_at": ts,
                            "source_fingerprint": row_fingerprint(original),
                        }
                    )
                    row_count += 1
            os.replace(tmp, output)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    return {
        "source": str(source),
        "output": str(output),
        "source_sha256": source_sha,
        "output_sha256": sha256_file(output),
        "rows": row_count,
        "columns": len(fields) + len(METADATA_COLUMNS),
        "batch_id": batch_id,
        "source_name": source_name,
        "ingested_at": ts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--ingested-at")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    result = prepare(
        args.source,
        args.output,
        batch_id=args.batch_id,
        source_name=args.source_name,
        ingested_at=args.ingested_at,
        expected_sha256=args.expected_sha256,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
