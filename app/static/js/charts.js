/* Chart.js charts for the dashboard. Chart is the vendored UMD global (static/vendor). */
/* global Chart */
import { shortDate } from './util.js';

let charts = {};   // {thisWeek: Chart, byWeek: Chart}

export function initCharts(project) {
  destroyCharts();
  if (project.project.goal_ties != null) {
    buildThisWeekChart(project.daily_log, project.project.daily_target);
    buildByWeekChart(project.daily_log, project.project.daily_target);
  } else {
    buildThisWeekTimbersChart(project);
    buildAccumulationChart(project);
  }
}

export function destroyCharts() {
  Object.values(charts).forEach(c => c && c.destroy());
  charts = {};
}

const toKey = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function thisWeekDays() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const weekStart = new Date(today);
  weekStart.setDate(today.getDate() - today.getDay()); // back to Sunday
  const days = [];
  for (let i = 0; i <= 6; i++) {
    const d = new Date(weekStart);
    d.setDate(weekStart.getDate() + i);
    if (d <= today) days.push(d);
  }
  return days;
}

function buildThisWeekChart(log, target) {
  const days = thisWeekDays();
  const labels = days.map(d => DAY_NAMES[d.getDay()]);
  const data = days.map(d => {
    const entry = log.find(e => e.date === toKey(d));
    return entry ? entry.ties : 0;
  });

  const ctx = document.getElementById('this-week-chart').getContext('2d');
  charts.thisWeek = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          type: 'bar',
          label: 'Ties',
          data,
          backgroundColor: data.map(v =>
            v === 0       ? 'rgba(120,128,138,.3)'
            : v >= target ? 'rgba(63,185,80,.75)'
                          : 'rgba(248,81,73,.75)'),
          borderColor: data.map(v =>
            v === 0       ? 'rgba(120,128,138,.55)'
            : v >= target ? 'rgba(63,185,80,1)'
                          : 'rgba(248,81,73,1)'),
          borderWidth: 1,
          borderRadius: 3,
        },
        {
          type: 'line',
          label: 'Target',
          data: days.map(() => target),
          borderColor: 'rgba(139,148,158,.6)',
          borderDash: [5, 5],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: chartOptions({ yLabel: 'Ties' }),
  });
}

function buildByWeekChart(log, target) {
  if (!log.length) return;

  const weeklyTarget = target * 6;
  const weekMap = {};
  log.forEach(e => {
    const d = new Date(e.date + 'T00:00:00');
    const sun = new Date(d);
    sun.setDate(d.getDate() - d.getDay());
    const key = toKey(sun);
    if (!weekMap[key]) weekMap[key] = { sun, total: 0 };
    weekMap[key].total += e.ties;
  });

  const weeks = Object.values(weekMap).sort((a, b) => a.sun - b.sun);

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const curSun = new Date(today);
  curSun.setDate(today.getDate() - today.getDay());
  const curKey = toKey(curSun);

  const isCurrent = weeks.map(w => toKey(w.sun) === curKey);
  const labels = weeks.map(w => shortDate(toKey(w.sun)));
  const data = weeks.map(w => w.total);

  const opts = chartOptions({ yLabel: 'Ties' });
  opts.plugins.tooltip.callbacks = {
    title: items => {
      const w = weeks[items[0].dataIndex];
      const sat = new Date(w.sun);
      sat.setDate(w.sun.getDate() + 6);
      const cur = isCurrent[items[0].dataIndex];
      return `${shortDate(toKey(w.sun))} to ${shortDate(toKey(sat))}${cur ? ' (in progress)' : ''}`;
    },
    label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()}`,
  };

  const ctx = document.getElementById('by-week-chart').getContext('2d');
  charts.byWeek = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Ties',
          data,
          backgroundColor: data.map((v, i) =>
            isCurrent[i]        ? 'rgba(51,75,101,.85)'
            : v >= weeklyTarget ? 'rgba(63,185,80,.75)'
                                : 'rgba(248,81,73,.75)'),
          borderColor: data.map((v, i) =>
            isCurrent[i]        ? 'rgba(51,75,101,1)'
            : v >= weeklyTarget ? 'rgba(63,185,80,1)'
                                : 'rgba(248,81,73,1)'),
          borderWidth: 1,
          borderRadius: 3,
        },
        {
          type: 'line',
          label: 'Weekly Target',
          data: weeks.map(() => weeklyTarget),
          borderColor: 'rgba(139,148,158,.6)',
          borderDash: [5, 5],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: opts,
  });
}

function chartOptions({ yLabel }) {
  return {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        labels: { color: '#66727f', font: { size: 11 } },
      },
      tooltip: {
        backgroundColor: '#1f2d3a',
        borderColor: '#1f2d3a',
        borderWidth: 1,
        titleColor: '#e6edf3',
        bodyColor: '#66727f',
        callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()}`,
        },
      },
    },
    scales: {
      x: {
        ticks:  { color: '#66727f', font: { size: 11 } },
        grid:   { color: 'rgba(0,0,0,0.07)' },
      },
      y: {
        ticks:  { color: '#66727f', font: { size: 11 } },
        grid:   { color: 'rgba(0,0,0,0.07)' },
        title:  { display: false },
      },
    },
  };
}

// ── Company timber charts ───────────────────────────────────────────────────────
function timbersByDate(project) {
  const map = {};
  const bump = (d, key, v) => { (map[d] = map[d] || { sw: 0, dr: 0, tie: 0 })[key] += v; };
  (project.switches || []).forEach(s => bump(s.date, 'sw', s.timbers.reduce((a, t) => a + t.actual, 0)));
  (project.derails  || []).forEach(d => bump(d.date, 'dr', d.timbers.reduce((a, t) => a + t.actual, 0)));
  (project.daily_log || []).forEach(e => bump(e.date, 'tie', e.ties));
  return map;
}

function buildThisWeekTimbersChart(project) {
  const canvas = document.getElementById('this-week-chart');
  if (!canvas) return;
  const map = timbersByDate(project);
  const days = thisWeekDays();
  const labels = days.map(d => DAY_NAMES[d.getDay()]);
  const data = days.map(d => { const m = map[toKey(d)]; return m ? m.sw + m.dr + m.tie : 0; });
  charts.thisWeek = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: { labels, datasets: [{
      label: 'Timbers', data,
      backgroundColor: 'rgba(51,75,101,.85)', borderColor: 'rgba(51,75,101,1)',
      borderWidth: 1, borderRadius: 3,
    }] },
    options: chartOptions({ yLabel: 'Timbers' }),
  });
}

function buildAccumulationChart(project) {
  const canvas = document.getElementById('by-week-chart');
  if (!canvas) return;
  const map = timbersByDate(project);
  const dates = Object.keys(map).sort();
  if (!dates.length) return;
  const weekMap = {};
  dates.forEach(ds => {
    const d = new Date(ds + 'T00:00:00');
    const sun = new Date(d); sun.setDate(d.getDate() - d.getDay());
    const m = map[ds];
    const k = toKey(sun);
    weekMap[k] = (weekMap[k] || 0) + m.sw + m.dr + m.tie;
  });
  const weeks = Object.keys(weekMap).sort();
  let cum = 0;
  const cumData = weeks.map(w => (cum += weekMap[w]));
  const labels = weeks.map(w => shortDate(w));
  charts.byWeek = new Chart(canvas.getContext('2d'), {
    data: { labels, datasets: [
      { type: 'bar', label: 'Per week', data: weeks.map(w => weekMap[w]),
        backgroundColor: 'rgba(63,185,80,.7)', borderColor: 'rgba(63,185,80,1)',
        borderWidth: 1, borderRadius: 3, order: 2 },
      { type: 'line', label: 'Cumulative', data: cumData,
        borderColor: 'rgba(227,179,65,1)', backgroundColor: 'rgba(227,179,65,.15)',
        borderWidth: 2, pointRadius: 2, fill: true, tension: .25, order: 1 },
    ] },
    options: chartOptions({ yLabel: 'Timbers' }),
  });
}
