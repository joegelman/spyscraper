# run_report.py
import argparse
from pathlib import Path

from ci.report import render_report_md
from ci.util import slugify


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", required=True)
    ap.add_argument("--base", default="data")
    args = ap.parse_args()

    slug = slugify(args.vendor)

    inp = Path(args.base) / slug / "synthesis" / "offering_semantics.json"
    out = Path(args.base) / slug / "report" / "offering_brief.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    render_report_md(
        offering_semantics_json=str(inp),
        out_md=str(out),
    )


if __name__ == "__main__":
    main()

