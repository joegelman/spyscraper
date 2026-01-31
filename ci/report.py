# ci/report.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ci.semantics import validate_semantics


def _md_escape(s: str) -> str:
    return (s or "").replace("\n", " ").strip()


def render_report_md(
    offering_semantics_json: str = "out/offering_semantics.json",
    out_md: str = "out/offering_brief.md",
) -> None:
    d = json.loads(Path(offering_semantics_json).read_text(encoding="utf-8"))
    ok, errs = validate_semantics(d)
    if not ok:
        raise ValueError("Invalid offering_semantics.json:\n- " + "\n- ".join(errs))

    vendor = d["vendor"]
    domain = d["domain"]

    lines = []
    lines.append(f"# {vendor} — Offering Map (Draft)")
    lines.append("")
    lines.append(f"- Domain: `{domain}`")
    lines.append("")

    lines.append("## Positioning")
    lines.append("")
    lines.append(_md_escape(d.get("positioning_one_liner", "")))
    lines.append("")

    cat = d.get("category") or []
    seg = d.get("target_segments") or []
    diff = d.get("differentiators") or []

    if cat:
        lines.append("**Category**")
        lines.append("")
        for x in cat:
            lines.append(f"- {_md_escape(x)}")
        lines.append("")

    if seg:
        lines.append("**Target segments**")
        lines.append("")
        for x in seg:
            lines.append(f"- {_md_escape(x)}")
        lines.append("")

    if diff:
        lines.append("**Differentiators**")
        lines.append("")
        for x in diff:
            lines.append(f"- {_md_escape(x)}")
        lines.append("")

    lines.append("## Modules")
    lines.append("")

    for m in d.get("modules", []):
        lines.append(f"### {m.get('name','')}")
        lines.append("")
        lines.append(f"**One-liner:** {_md_escape(m.get('one_liner',''))}")
        lines.append("")
        lines.append(_md_escape(m.get("description", "")))
        lines.append("")

        buyers = m.get("target_buyers") or []
        if buyers:
            lines.append("**Target buyers**")
            for b in buyers:
                lines.append(f"- {_md_escape(b)}")
            lines.append("")

        caps = m.get("key_capabilities") or []
        if caps:
            lines.append("**Key capabilities**")
            lines.append("")
            for c in caps:
                lines.append(f"- **{_md_escape(c.get('name',''))}** — {_md_escape(c.get('description',''))}")
                ev = c.get("evidence") or []
                for e in ev[:2]:
                    lines.append(f"  - Evidence: {e.get('url','')} — “{_md_escape(e.get('quote',''))}”")
            lines.append("")

        pps = m.get("proof_points") or []
        if pps:
            lines.append("**Proof points**")
            lines.append("")
            for pp in pps:
                lines.append(f"- {_md_escape(pp.get('claim',''))}")
                ev = pp.get("evidence") or []
                for e in ev[:2]:
                    lines.append(f"  - Evidence: {e.get('url','')} — “{_md_escape(e.get('quote',''))}”")
            lines.append("")

        srcs = m.get("source_urls") or []
        if srcs:
            lines.append("**Sources**")
            for u in srcs:
                lines.append(f"- {u}")
            lines.append("")

    nc = d.get("notable_claims") or []
    if nc:
        lines.append("## Notable claims")
        lines.append("")
        for pp in nc:
            lines.append(f"- {_md_escape(pp.get('claim',''))}")
            for e in (pp.get("evidence") or [])[:2]:
                lines.append(f"  - Evidence: {e.get('url','')} — “{_md_escape(e.get('quote',''))}”")
        lines.append("")

    missing = d.get("deemphasized_or_missing") or []
    if missing:
        lines.append("## Deemphasized / missing")
        lines.append("")
        for x in missing:
            lines.append(f"- {_md_escape(x)}")
        lines.append("")

    risks = d.get("risks_or_ambiguities") or []
    if risks:
        lines.append("## Risks / ambiguities")
        lines.append("")
        for x in risks:
            lines.append(f"- {_md_escape(x)}")
        lines.append("")

    urls_used = d.get("evidence_urls_used") or []
    if urls_used:
        lines.append("## Evidence appendix")
        lines.append("")
        for u in urls_used:
            lines.append(f"- {u}")
        lines.append("")

    Path(out_md).write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(f"Wrote {out_md}")

