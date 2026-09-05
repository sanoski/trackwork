/* Renders a project (or a worksite view of it) into the dashboard: cards, charts, switch and
   derail sections, and the log tables. Pure rendering over the project object. */
import { escHtml, formatDate, formatDuration, showView } from './util.js';
import { initCharts } from './charts.js';
import { buildSwitchSvg, buildDerailSvg } from './diagrams.js';

export function renderDashboard(project) {
  const summary = computeSummary(project);
  const meta    = project.project;
  const dash    = document.getElementById('dashboard');
  const sections = [];

  if (summary.hasGoal) {
    // Sponsored job: goal-centric header (progress toward a tie goal)
    sections.push(`<div class="stat-grid">${buildStatCards(summary, meta)}</div>`);
    sections.push(`
      <div class="progress-section">
        <div class="progress-header">
          <span class="progress-label">Overall Progress</span>
          <span class="progress-pct">${summary.pct}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width:${Math.min(summary.pct, 100)}%"></div>
        </div>
      </div>`);
  } else {
    // Company line work: no goal, so lead with accumulating totals
    sections.push(buildCompanyHero(summary, meta));
    sections.push(`<div class="stat-grid">${buildCompanyCards(summary)}</div>`);
  }

  sections.push(`
    <div class="charts-grid">
      <div class="chart-card"><h3>This Week</h3><canvas id="this-week-chart"></canvas></div>
      <div class="chart-card"><h3>${summary.hasGoal ? 'By Week' : 'Accumulation'}</h3><canvas id="by-week-chart"></canvas></div>
    </div>`);

  if (project.switches && project.switches.length) {
    sections.push(buildEntitySection('Switches', 'sw', project.switches, buildSwitchSvg));
  }
  if (project.derails && project.derails.length) {
    sections.push(buildEntitySection('Derails', 'dr', project.derails, buildDerailSvg));
  }

  if (project.daily_log && project.daily_log.length) {
    sections.push(`
      <div class="table-section">
        <h3>${summary.hasGoal ? 'Daily Activity Log' : 'Tie Production'}</h3>
        <div class="table-wrap">${buildDailyLogTable(project.daily_log, summary.relay > 0)}</div>
      </div>`);
  }

  if (project.equipment_downtime && project.equipment_downtime.length) {
    sections.push(`
      <div class="table-section">
        <h3>Equipment Downtime Log</h3>
        <div class="table-wrap">${buildDowntimeTable(project.equipment_downtime)}</div>
      </div>`);
  }

  dash.innerHTML = sections.join('');
  showView('dashboard');
  wireEntityTabs(dash);
  initCharts(project);
}

export function computeSummary(project) {
  const log    = project.daily_log || [];
  const meta   = project.project;
  const switches = project.switches || [];
  const derails  = project.derails  || [];

  const total  = log.reduce((s, e) => s + e.ties, 0);
  const relay  = log.reduce((s, e) => s + (e.relay_ties || 0), 0);
  const newTies = total - relay;
  const days   = log.length;
  const avg    = days > 0 ? total / days : 0;
  const hasGoal = meta.goal_ties != null;
  const remain = hasGoal ? meta.goal_ties - total : null;
  const vsSchedule = total - days * meta.daily_target;
  const today      = new Date(); today.setHours(0,0,0,0);
  const deadline   = meta.deadline ? new Date(meta.deadline + 'T00:00:00') : null;
  const daysLeft   = deadline ? Math.ceil((deadline - today) / 86400000) : null;
  const pct        = hasGoal ? +(total / meta.goal_ties * 100).toFixed(1) : null;
  const projected  = computeProjectedFinish(remain, avg);

  const [swPlanned, swActual] = sumEntities(switches);
  const [drPlanned, drActual] = sumEntities(derails);
  const totalTimbers = total + swActual + drActual;
  const allDates = [
    ...log.map(e => e.date), ...switches.map(s => s.date), ...derails.map(d => d.date),
  ].sort();
  const dateSet = new Set(allDates);
  const firstDate = allDates[0] || meta.created;

  return {
    total, relay, newTies, days, avg, remain, vsSchedule, daysLeft, pct, projected, deadline, hasGoal,
    swPlanned, swActual, swCount: switches.length,
    drPlanned, drActual, drCount: derails.length,
    totalTimbers, daysWorked: dateSet.size, firstDate,
  };
}

function sumEntities(list) {
  let planned = 0, actual = 0;
  list.forEach(e => e.timbers.forEach(t => { planned += t.planned; actual += t.actual; }));
  return [planned, actual];
}

export function entityTotals(e) {
  let planned = 0, actual = 0;
  e.timbers.forEach(t => { planned += t.planned; actual += t.actual; });
  return [planned, actual];
}

function computeProjectedFinish(remaining, avgDaily) {
  if (avgDaily <= 0 || remaining <= 0) return null;
  const d = new Date(); d.setHours(0,0,0,0);
  let left = remaining;
  let guard = 500;
  while (left > 0 && guard-- > 0) {
    d.setDate(d.getDate() + 1);
    const dow = d.getDay();
    if (dow >= 1 && dow <= 5) left -= avgDaily;
  }
  return left <= 0 ? new Date(d) : null;
}

function buildStatCards(s, meta) {
  const vsClass = s.vsSchedule >= 0 ? 'vs-positive' : 'vs-negative';
  const vsSign  = s.vsSchedule >= 0 ? '+' : '';
  const projStr = s.projected ? formatDate(s.projected) : '-';
  const goalSub = s.hasGoal ? `of ${meta.goal_ties.toLocaleString()} goal` : 'no goal set';
  const remainVal = s.hasGoal ? s.remain.toLocaleString() : '-';
  const remainSub = s.daysLeft != null ? `${s.daysLeft} days to deadline` : 'no deadline';

  const cards = [
    { label: 'Ties Installed',      value: s.total.toLocaleString(),           sub: goalSub,                                       cls: '' },
    { label: 'Ties Remaining',      value: remainVal,                          sub: remainSub,                                     cls: '' },
    { label: 'VS Schedule',         value: `${vsSign}${s.vsSchedule.toLocaleString()}`, sub: s.vsSchedule >= 0 ? 'Ahead of target' : 'Behind target', cls: vsClass },
    { label: 'Projected Finish',    value: projStr,                            sub: 'at current pace',                             cls: '' },
    { label: 'Daily Target',        value: meta.daily_target.toLocaleString(), sub: 'ties per day',                                cls: '' },
    { label: 'Avg Daily Output',    value: s.avg.toFixed(0),                   sub: `over ${s.days} working day${s.days !== 1 ? 's' : ''}`, cls: '' },
  ];

  return cards.map(c => `
    <div class="stat-card ${c.cls}">
      <div class="label">${c.label}</div>
      <div class="value">${c.value}</div>
      <div class="sub">${c.sub}</div>
    </div>
  `).join('');
}

// ── Company accumulator (no goal) ──────────────────────────────────────────────
function buildCompanyHero(s, meta) {
  const line = meta.line ? `${escHtml(meta.line)} &middot; ` : '';
  return `
    <div class="hero-accum">
      <div class="hero-accum-label">Total Timbers Installed</div>
      <div class="hero-accum-value">${s.totalTimbers.toLocaleString()}</div>
      <div class="hero-accum-sub">${line}since ${formatDate(s.firstDate)} &middot; ${s.daysWorked} day${s.daysWorked !== 1 ? 's' : ''} worked</div>
    </div>`;
}

function buildCompanyCards(s) {
  const cards = [];
  const swVar = s.swActual - s.swPlanned;
  cards.push({ label: 'Switch Timbers', value: s.swActual.toLocaleString(),
               sub: `${s.swPlanned.toLocaleString()} planned (${swVar >= 0 ? '+' : ''}${swVar})` });
  cards.push({ label: 'Switches', value: String(s.swCount), sub: 'completed' });
  if (s.drCount) {
    cards.push({ label: 'Derails', value: String(s.drCount),
                 sub: `${s.drActual} head block${s.drActual !== 1 ? 's' : ''}` });
  }
  if (s.total > 0) {
    cards.push({ label: 'New Ties', value: s.newTies.toLocaleString(), sub: 'plain track' });
    cards.push({ label: 'Relay Ties', value: s.relay.toLocaleString(), sub: 'reclaimed', cls: 'relay' });
  }
  cards.push({ label: 'Days Worked', value: String(s.daysWorked), sub: 'on this line' });
  return cards.map(c => `
    <div class="stat-card ${c.cls || ''}">
      <div class="label">${c.label}</div>
      <div class="value">${c.value}</div>
      <div class="sub">${c.sub}</div>
    </div>`).join('');
}

// ── Switch / derail sections ────────────────────────────────────────────────────
function shortName(e) {
  return e.name.replace(/\s+Switch$/i, '');
}

function buildEntitySection(title, group, entities, svgFn) {
  const tabs = entities.length === 1 ? '' : `<div class="entity-tabs">${
    entities.map((e, i) =>
      `<button class="entity-tab${i === 0 ? ' active' : ''}" data-group="${group}" data-index="${i}">${escHtml(shortName(e))}</button>`
    ).join('')
  }</div>`;
  const panels = entities.map((e, i) =>
    `<div class="entity-panel${i === 0 ? '' : ' hidden'}" data-group="${group}" data-index="${i}">${buildEntityPanel(e, svgFn, group === 'sw' ? 'switch' : 'derail')}</div>`
  ).join('');
  return `
    <div class="table-section entity-section">
      <h3>${title} <span class="count-pill">${entities.length}</span></h3>
      ${tabs}
      <div class="entity-panels">${panels}</div>
    </div>`;
}

function buildEntityPanel(e, svgFn, kind) {
  const [planned, actual] = entityTotals(e);
  const variance = actual - planned;
  const vClass = variance === 0 ? 'val-muted' : (variance > 0 ? 'val-positive' : 'val-negative');
  const vStr = variance === 0 ? 'on plan' : `${variance > 0 ? '+' : ''}${variance} vs planned`;
  const typeBadge = e.derail_type ? `<span class="badge badge-type">${escHtml(e.derail_type)}</span>` : '';
  return `
    <div class="entity-panel-inner">
      <div class="entity-diagram">${svgFn(e)}</div>
      <div class="entity-detail">
        <div class="entity-head">
          <span class="entity-name">${escHtml(e.name)}${typeBadge}</span>
          <span class="entity-date">${formatDate(e.date)}</span>
        </div>
        ${buildTimberTable(e)}
        <div class="entity-totals">
          <span>Planned <b>${planned}</b></span>
          <span>Actual <b>${actual}</b></span>
          <span class="${vClass}">${vStr}</span>
        </div>
        ${e.notes ? `<p class="entity-notes">${escHtml(e.notes)}</p>` : ''}
        <div class="entity-actions"><button type="button" class="row-act" data-act="edit-structure" data-kind="${kind}" data-id="${escHtml(e.id)}">Edit</button></div>
      </div>
    </div>`;
}

function buildTimberTable(e) {
  const rows = [...e.timbers].sort((a, b) => a.length - b.length).map(t => `
    <tr>
      <td>${t.length}'${t.head_block ? ' <span class="badge badge-hb">HB</span>' : ''}</td>
      <td>${t.planned || '<span class="val-muted">-</span>'}</td>
      <td>${t.actual || '<span class="val-muted">-</span>'}</td>
    </tr>`).join('');
  return `<table class="timber-table">
    <thead><tr><th>Length</th><th>Planned</th><th>Actual</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function wireEntityTabs(root) {
  root.querySelectorAll('.entity-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const { group, index } = btn.dataset;
      root.querySelectorAll(`.entity-tab[data-group="${group}"]`).forEach(b => b.classList.toggle('active', b === btn));
      root.querySelectorAll(`.entity-panel[data-group="${group}"]`).forEach(p =>
        p.classList.toggle('hidden', p.dataset.index !== index));
    });
  });
}

// ── Tables ───────────────────────────────────────────────────────────────────
function buildDailyLogTable(log, showRelay) {
  if (!log.length) return '<p class="text-muted text-sm" style="padding:.75rem">No entries yet.</p>';

  const rows = [...log].reverse().map(e => {
    const vs = e.vs_target;
    const vsCls = vs >= 0 ? 'val-positive' : 'val-negative';
    const vsStr = (vs >= 0 ? '+' : '') + vs.toLocaleString();
    const relay = e.relay_ties || 0;
    const tracks = e.tracks || [];
    const trackNote = tracks.length
      ? `<div class="track-note">${tracks.length === 1
            ? escHtml(tracks[0].track)
            : tracks.map(t => `${escHtml(t.track)}: ${t.ties.toLocaleString()}`).join(' · ')}</div>`
      : '';
    const tieCols = showRelay
      ? `<td>${(e.ties - relay).toLocaleString()}</td>
         <td>${relay ? relay.toLocaleString() : '<span class="val-muted">-</span>'}</td>
         <td>${e.ties.toLocaleString()}</td>`
      : `<td>${e.ties.toLocaleString()}</td>`;
    return `<tr>
      <td>${formatDate(e.date)}${trackNote}</td>
      <td>${e.day}</td>
      ${tieCols}
      <td class="${vsCls}">${vsStr}</td>
      <td>${e.running_total.toLocaleString()}</td>
      <td>${e.remaining != null ? e.remaining.toLocaleString() : '-'}</td>
      <td class="row-actions"><button type="button" class="row-act" data-act="edit-day" data-date="${e.date}">Edit</button></td>
    </tr>`;
  }).join('');

  const tieHeads = showRelay
    ? '<th>New</th><th>Relay</th><th>Total</th>'
    : '<th>Ties Done</th>';
  return `<table class="daily-table">
    <thead><tr>
      <th>Date</th><th>Day</th>${tieHeads}
      <th>vs Target</th><th>Running Total</th><th>Remaining</th><th class="row-actions"></th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function buildDowntimeTable(downtime) {
  if (!downtime.length) return '<p class="text-muted text-sm" style="padding:.75rem">No downtime recorded.</p>';

  const machineCounts = {};
  downtime.forEach(d => { machineCounts[d.machine] = (machineCounts[d.machine] || 0) + 1; });

  const rows = [...downtime].reverse().map(d => {
    const recurring = machineCounts[d.machine] > 1
      ? '<span class="badge badge-warn">Recurring</span>' : '';
    const duration = d.duration_minutes ? formatDuration(d.duration_minutes) : '<span class="val-muted">-</span>';
    const notesCls = d.notes ? '' : ' class="td-empty"';
    return `<tr>
      <td data-label="Date">${formatDate(d.date)}</td>
      <td data-label="Machine">${escHtml(d.machine)}${recurring}</td>
      <td data-label="Down At">${d.down_at || '<span class="val-muted">-</span>'}</td>
      <td data-label="Resumed">${d.resumed || '<span class="val-muted">-</span>'}</td>
      <td data-label="Duration">${duration}</td>
      <td data-label="Notes"${notesCls}>${d.notes ? escHtml(d.notes) : '<span class="val-muted">-</span>'}</td>
      <td class="row-actions" data-label=""><button type="button" class="row-act" data-act="edit-downtime" data-date="${d.date}" data-machine="${escHtml(d.machine)}" data-down-at="${d.down_at || ''}">Edit</button></td>
    </tr>`;
  }).join('');

  return `<table class="downtime-table">
    <thead><tr>
      <th>Date</th><th>Machine</th><th>Down At</th>
      <th>Resumed</th><th>Duration</th><th>Notes</th><th class="row-actions"></th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}
