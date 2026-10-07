from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .postgres import import_source_postgres, verify_contract
from .promotion import check_workstation, promote_batch
from .store import import_source, init_db, preview, stats

def parser():
    p = argparse.ArgumentParser(prog="meltano-leads-importer")
    p.add_argument("--db", default=os.getenv("LEADS_IMPORT_STAGING_DB", "runtime/raw-staging.db"))
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db")

    pv = sub.add_parser("preview")
    pv.add_argument("source")
    pv.add_argument("--sample-limit", type=int, default=5)

    imp = sub.add_parser("import")
    imp.add_argument("source")
    imp.add_argument("--batch-id")

    sub.add_parser("stats")

    chk = sub.add_parser("check-workstation")
    chk.add_argument("--url", default=os.getenv("LEADS_WORKSTATION_API_URL", "http://127.0.0.1:8765"))

    pr = sub.add_parser("promote-batch")
    pr.add_argument("batch_id")
    pr.add_argument("--url", default=os.getenv("LEADS_WORKSTATION_API_URL", "http://127.0.0.1:8765"))
    pr.add_argument("--limit", type=int)

    pgc = sub.add_parser("check-postgres")
    pgc.add_argument("--dsn", default=os.getenv("LEADS_IMPORT_POSTGRES_DSN"))

    pgi = sub.add_parser("import-postgres")
    pgi.add_argument("source")
    pgi.add_argument("--batch-id")
    pgi.add_argument("--dsn", default=os.getenv("LEADS_IMPORT_POSTGRES_DSN"))

    return p

def require_dsn(value):
    if not value:
        raise SystemExit("PostgreSQL DSN required via --dsn or LEADS_IMPORT_POSTGRES_DSN")
    return value

def main(argv=None):
    args = parser().parse_args(argv)
    db = Path(args.db)

    if args.command == "init-db":
        init_db(db)
        print(json.dumps({"ok": True, "db": str(db.resolve())}, indent=2))
        return 0
    if args.command == "preview":
        print(json.dumps(preview(args.source, args.sample_limit), indent=2, ensure_ascii=False))
        return 0
    if args.command == "import":
        print(json.dumps(import_source(db, args.source, args.batch_id), indent=2, ensure_ascii=False))
        return 0
    if args.command == "stats":
        print(json.dumps(stats(db), indent=2, ensure_ascii=False))
        return 0
    if args.command == "check-workstation":
        result = check_workstation(args.url)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1
    if args.command == "promote-batch":
        print(json.dumps(promote_batch(str(db), args.batch_id, args.url, args.limit), indent=2))
        return 0
    if args.command == "check-postgres":
        result = verify_contract(require_dsn(args.dsn))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1
    if args.command == "import-postgres":
        print(json.dumps(
            import_source_postgres(require_dsn(args.dsn), args.source, args.batch_id),
            indent=2,
            ensure_ascii=False,
        ))
        return 0
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
