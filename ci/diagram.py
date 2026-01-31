# ci/diagram.py
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote


def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_marchitecture_svg(
    offering_map_json: str = "out/offering_map.json",
    out_html: str = "out/marchitecture.html",
) -> None:
    om = json.loads(Path(offering_map_json).read_text(encoding="utf-8"))

    vendor = om.get("vendor", "Vendor")
    positioning = (om.get("positioning") or "").strip()

    pillars = om.get("pillars", []) or []
    if not pillars:
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"/><title>{_escape(vendor)} — Machitecture</title></head>
<body style="font-family: system-ui, sans-serif; padding: 24px;">
<h2>Nothing to render</h2>
<p><code>{_escape(offering_map_json)}</code> has no pillars. Check your allowlist and keep set.</p>
</body></html>"""
        Path(out_html).write_text(html, encoding="utf-8")
        print(f"Wrote {out_html} (empty)")
        return

    # Layout constants (top-down)
    W = 320
    H = 86
    PILLAR_W = 260
    PILLAR_H = 56
    GAP_X = 34
    GAP_Y = 36
    MARGIN = 40

    # Node positions
    nodes = []   # {id,label,title,bullets,url,x,y,w,h,level}
    edges = []   # (from,to)

    def add_node(node_id, label, title, bullets, url, x, y, w, h, level):
        nodes.append({
            "id": node_id,
            "label": label,
            "title": title,
            "bullets": bullets or [],
            "url": url or "",
            "x": x, "y": y, "w": w, "h": h,
            "level": level,
        })

    # Root centered above pillars
    # Compute pillar row width
    pillar_count = len(pillars)
    total_pillar_width = pillar_count * PILLAR_W + (pillar_count - 1) * GAP_X
    root_x = MARGIN + (total_pillar_width - W) / 2
    root_y = MARGIN

    root_id = f"ROOT::{vendor}"
    add_node(
        root_id,
        vendor,
        positioning or vendor,
        [positioning] if positioning else [],
        "",
        root_x,
        root_y,
        W,
        H,
        0
    )

    # Pillars row
    pillar_y = root_y + H + GAP_Y
    pillar_positions = {}
    for i, p in enumerate(pillars):
        x = MARGIN + i * (PILLAR_W + GAP_X)
        pid = f"P::{p['name']}"
        add_node(pid, p["name"], p["name"], [], "", x, pillar_y, PILLAR_W, PILLAR_H, 1)
        edges.append((root_id, pid))
        pillar_positions[pid] = x

    # Modules under each pillar, stacked
    max_bottom = pillar_y + PILLAR_H
    for i, p in enumerate(pillars):
        pid = f"P::{p['name']}"
        x = MARGIN + i * (PILLAR_W + GAP_X) - (W - PILLAR_W) / 2  # center modules under pillar
        y = pillar_y + PILLAR_H + GAP_Y

        for m in (p.get("modules") or [])[:10]:
            mid = f"M::{p['name']}::{m['name']}"
            bullets = (m.get("bullets") or [])[:4]
            url = m.get("url") or ""
            add_node(mid, m["name"], m["name"], bullets, url, x, y, W, H, 2)
            edges.append((pid, mid))
            y += H + GAP_Y
            max_bottom = max(max_bottom, y)

    svg_w = int(MARGIN * 2 + total_pillar_width + 120)
    svg_h = int(max_bottom + 80)

    # Edge paths (top-down)
    edge_paths = []
    for s, t in edges:
        sn = next(n for n in nodes if n["id"] == s)
        tn = next(n for n in nodes if n["id"] == t)

        sx = sn["x"] + sn["w"] / 2
        sy = sn["y"] + sn["h"]
        tx = tn["x"] + tn["w"] / 2
        ty = tn["y"]

        c1x, c1y = sx, sy + 18
        c2x, c2y = tx, ty - 18
        d = f"M {sx:.1f},{sy:.1f} C {c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {tx:.1f},{ty:.1f}"
        edge_paths.append(d)

    # Node SVG
    node_svgs = []
    for n in nodes:
        x, y, w, h = n["x"], n["y"], n["w"], n["h"]
        label = _escape(n["label"])
        title = _escape(n["title"])
        bullets = n["bullets"] or []
        url = _escape(n["url"])
        data_url = quote(n.get("url", ""), safe=":/?#[]@!$&'()*+,;=%") if url else ""
        cursor = "pointer" if url else "default"

        # Render bullets inside box
        lines = []
        # Title line
        lines.append(f'<text class="t" x="12" y="22">{label[:38]}</text>')
        # Bullets
        by = 40
        for b in bullets[:4]:
            b = _escape(b)
            lines.append(f'<text class="b" x="18" y="{by}">• {b[:52]}</text>')
            by += 16

        node_svgs.append(f"""
<g class="node" data-url="{data_url}" transform="translate({x},{y})" style="cursor:{cursor}">
  <title>{title}</title>
  <rect class="box" width="{w}" height="{h}" rx="10" ry="10"></rect>
  {''.join(lines)}
</g>
""")

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{_escape(vendor)} — Machitecture</title>
  <style>
    html, body {{ height:100%; margin:0; }}
    #wrap {{ height:100%; width:100%; overflow:hidden; background:#fff; font-family: system-ui, sans-serif; }}
    #bar {{
      position: fixed; top: 10px; left: 10px; z-index: 2;
      background: rgba(255,255,255,0.95); padding: 10px 12px;
      border: 1px solid #ddd; border-radius: 8px;
      font-size: 13px; max-width: 560px;
    }}
    .box {{ fill:#fff; stroke:#111; stroke-width:1.2; }}
    .edge {{ fill:none; stroke:#999; stroke-width:1.2; }}
    .t {{ font-size:12px; font-weight:600; fill:#111; }}
    .b {{ font-size:11px; fill:#111; }}
    .node:hover .box {{ stroke-width:2.2; }}
  </style>
</head>
<body>
<div id="bar">
  <div><b>{_escape(vendor)} — Machitecture</b></div>
  <div style="margin-top:6px;">{_escape(positioning)}</div>
  <div style="margin-top:8px;">Pan: drag background · Zoom: mousewheel · Click box: open evidence URL</div>
</div>

<div id="wrap">
<svg id="svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">
  <g id="camera">
    {''.join(f'<path class="edge" d="{d}"></path>' for d in edge_paths)}
    {''.join(node_svgs)}
  </g>
</svg>
</div>

<script>
(function() {{
  const svg = document.getElementById('svg');
  let viewBox = svg.viewBox.baseVal;
  let isPanning = false;
  let start = {{x:0, y:0}};
  let vbStart = {{x:viewBox.x, y:viewBox.y}};

  svg.addEventListener('mousedown', (e) => {{
    if (e.target.closest('.node')) return;
    isPanning = true;
    start = {{x: e.clientX, y: e.clientY}};
    vbStart = {{x: viewBox.x, y: viewBox.y}};
  }});
  window.addEventListener('mouseup', () => isPanning = false);
  window.addEventListener('mousemove', (e) => {{
    if (!isPanning) return;
    const dx = (e.clientX - start.x) * (viewBox.width / svg.clientWidth);
    const dy = (e.clientY - start.y) * (viewBox.height / svg.clientHeight);
    viewBox.x = vbStart.x - dx;
    viewBox.y = vbStart.y - dy;
  }});

  svg.addEventListener('wheel', (e) => {{
    e.preventDefault();
    const scale = (e.deltaY < 0) ? 0.9 : 1.1;

    const mx = e.offsetX / svg.clientWidth * viewBox.width + viewBox.x;
    const my = e.offsetY / svg.clientHeight * viewBox.height + viewBox.y;

    const newW = viewBox.width * scale;
    const newH = viewBox.height * scale;

    viewBox.x = mx - (mx - viewBox.x) * (newW / viewBox.width);
    viewBox.y = my - (my - viewBox.y) * (newH / viewBox.height);
    viewBox.width = newW;
    viewBox.height = newH;
  }}, {{ passive: false }});

  svg.addEventListener('click', (e) => {{
    const n = e.target.closest('.node');
    if (!n) return;
    const u = decodeURIComponent(n.getAttribute('data-url') || "");
    if (u) window.open(u, "_blank");
  }});
}})();
</script>
</body>
</html>
"""
    Path(out_html).write_text(html, encoding="utf-8")
    print(f"Wrote {out_html}")

