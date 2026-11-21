import argparse
import json
from pathlib import Path
import sys

from .intake import catalog, inspect_records
from .pipeline import analyze, query, read_json, status


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mechcurve")
    cmds = parser.add_subparsers(dest="cmd", required=True)
    scan = cmds.add_parser("inspect")
    scan.add_argument("input")
    scan.add_argument("--notes")
    cmds.add_parser("protocols")
    run = cmds.add_parser("analyze")
    run.add_argument("input")
    run.add_argument("--output")
    run.add_argument("--notes")
    run.add_argument("--lang", choices=("zh", "en"), default="zh")
    check = cmds.add_parser("verify")
    check.add_argument("run")
    for name in ("cycles", "evidence"):
        p = cmds.add_parser(name)
        p.add_argument("run")
        p.add_argument("--record", required=True)
        if name == "cycles":
            p.add_argument("--cycle", type=int)
        else:
            p.add_argument("--row", type=int, required=True)
            p.add_argument("--radius", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "analyze":
            result = analyze(
                args.input,
                args.output,
                read_json(Path(args.notes)) if args.notes else None,
                lang=args.lang,
            )
        elif args.cmd == "inspect":
            result = inspect_records(
                args.input, read_json(Path(args.notes)) if args.notes else None
            )
        elif args.cmd == "protocols":
            result = catalog()
        elif args.cmd == "verify":
            result = status(Path(args.run))
        else:
            result = query(
                args.run,
                args.record,
                getattr(args, "cycle", None),
                getattr(args, "row", None),
                getattr(args, "radius", 3),
            )
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 2 if isinstance(result, dict) and result.get("status") == "partial" else 0


if __name__ == "__main__":
    sys.exit(main())
