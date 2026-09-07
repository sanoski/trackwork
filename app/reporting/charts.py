"""Inline-SVG chart builders for the report, pure string functions, no dependency.

WeasyPrint runs no JavaScript, so Chart.js (the portal's charting) can't be reused server-side.
These emit self-contained `<svg>` strings (internal `<style>`, brand palette) that render
identically in the browser preview and in the WeasyPrint PDF. Datasets are tiny (a handful of
weeks / <=7 days / 4 composition segments), so hand-built SVG beats pulling in matplotlib/pygal.
"""
from __future__ import annotations

from html import escape

# Brand palette, mirrors the CSS :root vars so the PDF matches the portal.
NAVY = "#334b65"
RED = "#c1151b"
GREEN = "#1a7f4b"
YELLOW = "#d99a16"
WOOD = "#7d4a26"
MUTED = "#66727f"
BORDER = "#d9dee4"
GRID = "#eef1f4"

_FONT = '"DejaVu Sans", "Liberation Sans", sans-serif'
_STYLE = (
    f'<style>text{{font-family:{_FONT}}}'
    f'.v{{font-size:9px;fill:{MUTED}}}.c{{font-size:8.5px;fill:{MUTED}}}'
    f'.t{{font-size:8px;fill:{YELLOW}}}.lg{{font-size:8.5px;fill:#25323f}}</style>'
)


def _fmt(v: float) -> str:
    return f"{int(round(v)):,}"


def _svg(width: int, height: int, body: str) -> str:
    return (f'<svg viewBox="0 0 {width} {height}" style="width:100%;height:auto" '
            f'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">'
            f'{_STYLE}{body}</svg>')


def _empty(width: int, height: int, msg: str) -> str:
    return _svg(width, height,
                f'<text x="{width/2:.0f}" y="{height/2:.0f}" text-anchor="middle" '
                f'class="c">{escape(msg)}</text>')


def bar_chart(labels, values, *, color=NAVY, target=None, width=340, height=100,
              value_labels=True) -> str:
    """Vertical bars with value labels above and category labels below; optional dashed
    target line. Used for weekly/daily production and per-worksite totals."""
    values = list(values)
    if not values or max(values) <= 0:
        return _empty(width, height, "No data for this period.")
    lm, rm, tm, bm = 10, 10, 16, 24
    pw, ph = width - lm - rm, height - tm - bm
    maxv = max(values + ([target] if target else []) + [1]) * 1.18
    n = len(values)
    slot = pw / n
    bw = min(slot * 0.6, 46)
    base_y = tm + ph
    parts = [f'<line x1="{lm}" y1="{base_y}" x2="{lm+pw}" y2="{base_y}" '
             f'stroke="{BORDER}" stroke-width="1"/>']
    for i, (lab, v) in enumerate(zip(labels, values)):
        x = lm + i * slot + (slot - bw) / 2
        h = ph * (v / maxv)
        y = base_y - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" '
                     f'height="{max(h, 0.6):.1f}" rx="2" fill="{color}"/>')
        if value_labels and v:
            parts.append(f'<text x="{x+bw/2:.1f}" y="{y-3:.1f}" text-anchor="middle" '
                         f'class="v">{_fmt(v)}</text>')
        parts.append(f'<text x="{x+bw/2:.1f}" y="{base_y+12:.1f}" text-anchor="middle" '
                     f'class="c">{escape(str(lab))}</text>')
    if target:
        ty = base_y - ph * (target / maxv)
        parts.append(f'<line x1="{lm}" y1="{ty:.1f}" x2="{lm+pw}" y2="{ty:.1f}" '
                     f'stroke="{YELLOW}" stroke-width="1.2" stroke-dasharray="5 3"/>')
        parts.append(f'<text x="{lm+pw:.1f}" y="{ty-3:.1f}" text-anchor="end" '
                     f'class="t">target {_fmt(target)}</text>')
    return _svg(width, height, "".join(parts))


def line_chart(labels, series, *, width=340, height=100) -> str:
    """One or more cumulative line series over the same x labels. `series` is a list of
    (name, color, values). Sponsored uses two series (actual vs target); company uses one."""
    all_vals = [v for _, _, vals in series for v in vals]
    if not all_vals or max(all_vals) <= 0:
        return _empty(width, height, "No data recorded yet.")
    lm, rm, tm, bm = 34, 8, 16, 22
    pw, ph = width - lm - rm, height - tm - bm
    maxv = max(all_vals + [1]) * 1.1
    n = len(labels)
    xstep = pw / (n - 1) if n > 1 else 0
    base_y = tm + ph
    parts = []
    for frac in (0.0, 0.5, 1.0):
        gy = base_y - ph * frac
        parts.append(f'<line x1="{lm}" y1="{gy:.1f}" x2="{lm+pw}" y2="{gy:.1f}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{lm-4}" y="{gy+3:.1f}" text-anchor="end" '
                     f'class="c">{_fmt(maxv*frac)}</text>')
    for name, color, vals in series:
        if n == 1:
            cy = base_y - ph * (vals[0] / maxv)
            parts.append(f'<circle cx="{lm:.1f}" cy="{cy:.1f}" r="2.4" fill="{color}"/>')
            continue
        pts = " ".join(f"{lm+i*xstep:.1f},{base_y-ph*(v/maxv):.1f}" for i, v in enumerate(vals))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" '
                     f'stroke-width="2" stroke-linejoin="round"/>')
    # sparse x labels (first, middle, last) to avoid clutter
    idxs = sorted({0, n // 2, n - 1}) if n > 1 else [0]
    for i in idxs:
        parts.append(f'<text x="{lm+i*xstep:.1f}" y="{base_y+12:.1f}" text-anchor="middle" '
                     f'class="c">{escape(str(labels[i]))}</text>')
    # legend (only when more than one series)
    if len(series) > 1:
        lx = lm
        for name, color, _ in series:
            parts.append(f'<rect x="{lx}" y="2" width="14" height="4" fill="{color}"/>')
            parts.append(f'<text x="{lx+18}" y="6" class="lg">{escape(name)}</text>')
            lx += 22 + len(name) * 5.2
    return _svg(width, height, "".join(parts))


def stacked_bar(segments, *, width=340, height=64) -> str:
    """Horizontal composition bar with a legend below. `segments` is a list of
    (label, value, color). Reads cleanly across both renderers (no arc math)."""
    segments = [(l, v, c) for (l, v, c) in segments if v > 0]
    total = sum(v for _, v, _ in segments)
    if total <= 0:
        return _empty(width, height, "No work to break down yet.")
    lm, rm = 10, 10
    bar_y, bar_h = 12, 28
    pw = width - lm - rm
    parts = []
    x = lm
    for lab, v, color in segments:
        w = pw * (v / total)
        parts.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{w:.1f}" height="{bar_h}" '
                     f'fill="{color}"/>')
        if w > 26:
            parts.append(f'<text x="{x+w/2:.1f}" y="{bar_y+bar_h/2+3:.1f}" '
                         f'text-anchor="middle" style="font-size:9px;fill:#fff">{_fmt(v)}</text>')
        x += w
    # legend, wraps to further rows if needed; the SVG grows so no row is ever clipped
    lx, ly = lm, bar_y + bar_h + 16
    for lab, v, color in segments:
        label = f"{lab} {_fmt(v)}"
        seg_w = 16 + len(label) * 5.4
        if lx + seg_w > width - rm and lx > lm:
            lx, ly = lm, ly + 14
        parts.append(f'<rect x="{lx}" y="{ly-7}" width="9" height="9" rx="1.5" fill="{color}"/>')
        parts.append(f'<text x="{lx+13}" y="{ly}" class="lg">{escape(label)}</text>')
        lx += seg_w
    return _svg(width, max(height, ly + 6), "".join(parts))
