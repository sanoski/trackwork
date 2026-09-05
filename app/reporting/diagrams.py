"""Switch / derail plan-view SVG diagrams for the report.

Ported from the portal's `app.js` `buildSwitchSvg` / `buildDerailSvg` (identical viewBox,
constants, and geometry) so the web dashboard and the PDF render the same picture from ONE
definition. The emitted `<svg>` is self-contained (an internal `<style>` with concrete brand
colors) because WeasyPrint can't see the portal's style.css. Replaces the old ReportLab
`_switch_drawing`/`_derail_drawing`, and is simpler, since SVG needs no y-flip or inch scaling.
"""
from __future__ import annotations

from html import escape

# Concrete colors mirroring style.css `.switch-svg .*` (no CSS vars, self-contained).
_STYLE = (
    '<style>'
    'text{font-family:"DejaVu Sans","Liberation Sans",sans-serif}'
    '.tmb{fill:#7d4a26;stroke:#c47f3d;stroke-width:1}'
    '.tmb-hb{fill:#d99a16;stroke:#f2d27a;stroke-width:1}'
    '.rail{stroke:#9aa4af;stroke-width:3;fill:none;stroke-linecap:round}'
    '.rail-div{stroke:#9aa4af;stroke-width:3;fill:none;stroke-linecap:round;'
    'stroke-linejoin:round;opacity:.9}'
    '.rail-thin{stroke:#9aa4af;stroke-width:1.4;fill:none}'
    '.stand{stroke:#9aa4af;stroke-width:1.4;fill:#ffffff}'
    '.frog{fill:#ee8b3c}'
    '.frog-lbl{fill:#ee8b3c;font-size:9px;font-weight:700;paint-order:stroke;'
    'stroke:#ffffff;stroke-width:2.5px;stroke-linejoin:round}'
    '.tmb-len{fill:#66727f;font-size:10px}'
    '.tmb-cnt{fill:#25323f;font-size:10px;font-weight:700}'
    '.derail-wedge{fill:#c1151b}'
    '.derail-lbl{fill:#c1151b;font-size:9px;font-weight:700;paint-order:stroke;'
    'stroke:#ffffff;stroke-width:2.5px;stroke-linejoin:round}'
    '</style>'
)


def group_timbers(entity):
    """[[length, count, head_block], ...] over installed timbers (actual > 0), sorted by
    length, runs of equal (length, head_block) merged. The one shared grouping the JS twin and
    the old ReportLab code each reimplemented."""
    groups = []
    for t in sorted([t for t in entity.timbers if t.actual > 0], key=lambda t: t.length):
        if groups and groups[-1][0] == t.length and groups[-1][2] == bool(t.head_block):
            groups[-1][1] += t.actual
        else:
            groups.append([t.length, t.actual, bool(t.head_block)])
    return groups


def _bars_and_labels(groups, *, cx, label_w, fan_w, row_h, bar_h, group_gap, top_y,
                     w_min, w_max):
    n_rows = sum(g[1] for g in groups)
    lens = [g[0] for g in groups]
    min_l, max_l = min(lens), max(lens)
    span = (max_l - min_l) or 1

    def bw(length):
        return w_min + (w_max - w_min) * (length - min_l) / span

    bars, labels, y = [], [], top_y
    for gi, (length, count, hb) in enumerate(groups):
        w = bw(length)
        x = cx - w / 2
        g_top = y
        cls = "tmb-hb" if hb else "tmb"
        for _ in range(count):
            bars.append(f'<rect x="{x:.1f}" y="{y+(row_h-bar_h)/2:.1f}" width="{w:.1f}" '
                        f'height="{bar_h}" rx="1.5" class="{cls}"/>')
            y += row_h
        mid = (g_top + y) / 2 + 3
        labels.append(f'<text x="{label_w-8}" y="{mid:.1f}" class="tmb-len" '
                      f'text-anchor="end">{length}\'{" HB" if hb else ""}</text>')
        labels.append(f'<text x="{label_w+fan_w+8}" y="{mid:.1f}" '
                      f'class="tmb-cnt">&#215;{count}</text>')
        if gi < len(groups) - 1:
            y += group_gap
    return "".join(bars), "".join(labels), n_rows


def switch_svg(entity) -> str:
    """Plan-view turnout: one bar per installed timber, grouped by length into a fan growing
    toward the frog; two through-rails + a diverging rail through the frog; a switch stand."""
    groups = group_timbers(entity)
    if not groups:
        return ('<svg viewBox="0 0 200 30" class="switch-svg" style="width:100%;height:auto" '
                f'xmlns="http://www.w3.org/2000/svg">{_STYLE}'
                '<text x="8" y="18" class="tmb-cnt">no timbers installed</text></svg>')

    label_w, fan_w, count_w = 46, 196, 44
    gauge, row_h, bar_h, group_gap, pad_top, pad_bot = 22, 14, 9, 4, 18, 16
    W = label_w + fan_w + count_w
    cx = label_w + fan_w / 2
    top_y = pad_top
    n_rows = sum(g[1] for g in groups)
    body_h = n_rows * row_h + (len(groups) - 1) * group_gap
    bot_y = top_y + body_h
    H = bot_y + pad_bot

    bars, labels, _ = _bars_and_labels(groups, cx=cx, label_w=label_w, fan_w=fan_w,
                                       row_h=row_h, bar_h=bar_h, group_gap=group_gap,
                                       top_y=top_y, w_min=86, w_max=fan_w)
    rail_l, rail_r = cx - gauge / 2, cx + gauge / 2
    rails = (f'<line x1="{rail_l}" y1="{top_y-4}" x2="{rail_l}" y2="{bot_y+4}" class="rail"/>'
             f'<line x1="{rail_r}" y1="{top_y-4}" x2="{rail_r}" y2="{bot_y+4}" class="rail"/>')
    frog_y = top_y + body_h * 0.6
    heel_x = rail_r + fan_w * 0.22
    diverge = (f'<polyline points="{cx},{top_y-4} {rail_r:.1f},{frog_y:.1f} '
               f'{heel_x:.1f},{bot_y+4:.1f}" class="rail rail-div"/>')
    frog = (f'<polygon points="{rail_r-5},{frog_y-5:.1f} {rail_r+5},{frog_y-5:.1f} '
            f'{rail_r},{frog_y+5:.1f}" class="frog"/>'
            f'<text x="{rail_r+9}" y="{frog_y+3:.1f}" class="frog-lbl">FROG</text>')
    stand_y = top_y - 7
    stand = (f'<line x1="{rail_l}" y1="{stand_y}" x2="{cx-30}" y2="{stand_y}" class="rail-thin"/>'
             f'<circle cx="{cx-33}" cy="{stand_y}" r="3.2" class="stand"/>')
    return (f'<svg viewBox="0 0 {W} {H}" class="switch-svg" style="width:100%;height:auto" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="Switch turnout timber diagram">'
            f'{_STYLE}{bars}{rails}{diverge}{frog}{stand}{labels}</svg>')


def derail_svg(entity) -> str:
    """A derail: a wedge clamped on the rail over its (usually head-block) timbers."""
    groups = group_timbers(entity)
    label_w, fan_w, count_w = 46, 150, 44
    gauge, row_h, bar_h, group_gap, pad_top, pad_bot = 22, 14, 9, 4, 26, 14
    W = label_w + fan_w + count_w
    cx = label_w + fan_w / 2
    top_y = pad_top
    n_rows = sum(g[1] for g in groups)
    body_h = (n_rows * row_h + (len(groups) - 1) * group_gap) if n_rows else 0
    bot_y = top_y + body_h
    H = max(bot_y, top_y + 10) + pad_bot

    if n_rows:
        bars, labels, _ = _bars_and_labels(groups, cx=cx, label_w=label_w, fan_w=fan_w,
                                           row_h=row_h, bar_h=bar_h, group_gap=group_gap,
                                           top_y=top_y, w_min=96, w_max=fan_w)
    else:
        bars = ""
        labels = (f'<text x="{cx}" y="{top_y+4}" class="tmb-cnt" '
                  f'text-anchor="middle">portable &#8212; no timbers</text>')

    rail_l, rail_r = cx - gauge / 2, cx + gauge / 2
    r_top, r_bot = 8, max(bot_y + 4, 8 + 26)
    rails = (f'<line x1="{rail_l}" y1="{r_top}" x2="{rail_l}" y2="{r_bot}" class="rail"/>'
             f'<line x1="{rail_r}" y1="{r_top}" x2="{rail_r}" y2="{r_bot}" class="rail"/>')
    wy = top_y - 13
    wedge = (f'<polygon points="{rail_r-7},{wy} {rail_r+7},{wy} {rail_r},{wy+11}" '
             f'class="derail-wedge"/>'
             f'<text x="{rail_r+11}" y="{wy+8}" class="derail-lbl">derail</text>')
    return (f'<svg viewBox="0 0 {W} {H}" class="switch-svg" style="width:100%;height:auto" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Derail diagram">'
            f'{_STYLE}{bars}{rails}{wedge}{labels}</svg>')
