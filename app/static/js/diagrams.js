/* Switch and derail plan-view SVG diagrams. Mirrored server-side in app/reporting/diagrams.py
   so the portal and the PDF draw the same picture. */

function groupInstalled(timbers) {
  const installed = [...(timbers || [])].filter(t => t.actual > 0).sort((a, b) => a.length - b.length);
  const groups = [];
  installed.forEach(t => {
    const last = groups[groups.length - 1];
    if (last && last.length === t.length && last.head_block === !!t.head_block) last.count += t.actual;
    else groups.push({ length: t.length, count: t.actual, head_block: !!t.head_block });
  });
  return groups;
}

/* Plan-view turnout. One bar per installed timber (actual > 0), grouped by length into a fan
   growing toward the frog; two through-rails; a diverging rail kinking through the frog; gold
   head-blocks; a switch stand at the points. */
export function buildSwitchSvg(s) {
  const groups = groupInstalled(s.timbers);
  if (!groups.length) return '<svg viewBox="0 0 200 30" class="switch-svg"><text x="8" y="18" class="tmb-cnt">no timbers installed</text></svg>';
  const nRows = groups.reduce((a, g) => a + g.count, 0);

  const labelW = 46, fanW = 196, countW = 44;
  const gauge = 22, rowH = 14, barH = 9, groupGap = 4, padTop = 18, padBot = 16;
  const W = labelW + fanW + countW, cx = labelW + fanW / 2;
  const topY = padTop, bodyH = nRows * rowH + (groups.length - 1) * groupGap;
  const botY = topY + bodyH, H = botY + padBot;

  const lens = groups.map(g => g.length);
  const minL = Math.min(...lens), maxL = Math.max(...lens), span = (maxL - minL) || 1;
  const wMin = 86, wMax = fanW, barW = L => wMin + (wMax - wMin) * (L - minL) / span;

  let bars = '', labels = '', y = topY;
  groups.forEach((g, gi) => {
    const w = barW(g.length), x = cx - w / 2, gTop = y;
    for (let k = 0; k < g.count; k++) {
      bars += `<rect x="${x.toFixed(1)}" y="${(y + (rowH - barH) / 2).toFixed(1)}" width="${w.toFixed(1)}" height="${barH}" rx="1.5" class="${g.head_block ? 'tmb-hb' : 'tmb'}"/>`;
      y += rowH;
    }
    const mid = (gTop + y) / 2 + 3;
    labels += `<text x="${labelW - 8}" y="${mid.toFixed(1)}" class="tmb-len" text-anchor="end">${g.length}'${g.head_block ? ' HB' : ''}</text>`;
    labels += `<text x="${labelW + fanW + 8}" y="${mid.toFixed(1)}" class="tmb-cnt">&#215;${g.count}</text>`;
    if (gi < groups.length - 1) y += groupGap;
  });

  const railL = cx - gauge / 2, railR = cx + gauge / 2;
  const rails = `<line x1="${railL}" y1="${topY - 4}" x2="${railL}" y2="${botY + 4}" class="rail"/>`
              + `<line x1="${railR}" y1="${topY - 4}" x2="${railR}" y2="${botY + 4}" class="rail"/>`;
  const frogY = topY + bodyH * 0.6, heelX = railR + fanW * 0.22;
  const diverge = `<polyline points="${cx},${topY - 4} ${railR.toFixed(1)},${frogY.toFixed(1)} ${heelX.toFixed(1)},${(botY + 4).toFixed(1)}" class="rail rail-div"/>`;
  const frog = `<polygon points="${railR - 5},${(frogY - 5).toFixed(1)} ${railR + 5},${(frogY - 5).toFixed(1)} ${railR},${(frogY + 5).toFixed(1)}" class="frog"/>`
             + `<text x="${railR + 9}" y="${(frogY + 3).toFixed(1)}" class="frog-lbl">FROG</text>`;
  const standY = topY - 7;
  const stand = `<line x1="${railL}" y1="${standY}" x2="${cx - 30}" y2="${standY}" class="rail-thin"/>`
              + `<circle cx="${cx - 33}" cy="${standY}" r="3.2" class="stand"/>`;
  return `<svg viewBox="0 0 ${W} ${H}" class="switch-svg" role="img" aria-label="Switch turnout timber diagram">${bars}${rails}${diverge}${frog}${stand}${labels}</svg>`;
}

/* A derail: a wedge clamped on the rail, sitting over its (usually head-block) timbers. */
export function buildDerailSvg(d) {
  const groups = groupInstalled(d.timbers);
  const nRows = groups.reduce((a, g) => a + g.count, 0);

  const labelW = 46, fanW = 150, countW = 44;
  const gauge = 22, rowH = 14, barH = 9, groupGap = 4, padTop = 26, padBot = 14;
  const W = labelW + fanW + countW, cx = labelW + fanW / 2;
  const topY = padTop, bodyH = nRows ? nRows * rowH + (groups.length - 1) * groupGap : 0;
  const botY = topY + bodyH, H = Math.max(botY, topY + 10) + padBot;

  let bars = '', labels = '', y = topY;
  if (nRows) {
    const lens = groups.map(g => g.length);
    const minL = Math.min(...lens), maxL = Math.max(...lens), span = (maxL - minL) || 1;
    const wMin = 96, wMax = fanW, barW = L => wMin + (wMax - wMin) * (L - minL) / span;
    groups.forEach((g, gi) => {
      const w = barW(g.length), x = cx - w / 2, gTop = y;
      for (let k = 0; k < g.count; k++) {
        bars += `<rect x="${x.toFixed(1)}" y="${(y + (rowH - barH) / 2).toFixed(1)}" width="${w.toFixed(1)}" height="${barH}" rx="1.5" class="${g.head_block ? 'tmb-hb' : 'tmb'}"/>`;
        y += rowH;
      }
      const mid = (gTop + y) / 2 + 3;
      labels += `<text x="${labelW - 8}" y="${mid.toFixed(1)}" class="tmb-len" text-anchor="end">${g.length}'${g.head_block ? ' HB' : ''}</text>`;
      labels += `<text x="${labelW + fanW + 8}" y="${mid.toFixed(1)}" class="tmb-cnt">&#215;${g.count}</text>`;
      if (gi < groups.length - 1) y += groupGap;
    });
  } else {
    labels = `<text x="${cx}" y="${topY + 4}" class="tmb-cnt" text-anchor="middle">portable: no timbers</text>`;
  }

  const railL = cx - gauge / 2, railR = cx + gauge / 2;
  const rTop = 8, rBot = Math.max(botY + 4, rTop + 26);
  const rails = `<line x1="${railL}" y1="${rTop}" x2="${railL}" y2="${rBot}" class="rail"/>`
              + `<line x1="${railR}" y1="${rTop}" x2="${railR}" y2="${rBot}" class="rail"/>`;
  const wy = topY - 13;
  const wedge = `<polygon points="${railR - 7},${wy} ${railR + 7},${wy} ${railR},${wy + 11}" class="derail-wedge"/>`
              + `<text x="${railR + 11}" y="${wy + 8}" class="derail-lbl">derail</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" class="switch-svg" role="img" aria-label="Derail diagram">${bars}${rails}${wedge}${labels}</svg>`;
}
