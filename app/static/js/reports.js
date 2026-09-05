/* The Generate Report wizard: scope, period, content toggles, live preview, and send. */
import { state } from './state.js';
import { api } from './api.js';
import { escHtml, showMsg, clearMsg, locationName } from './util.js';

/* Scope follows the view (current project + selected worksite) but every control is also
   explicit and overridable here. Defaults reproduce the overview report (server-side
   default_options), so leaving everything alone matches the scheduled weekly report. */
export function openReportModal() {
  const proj = state.project;
  const isCompany = !!(proj && proj.project.kind === 'company');

  let scope = proj ? proj.project.name : 'the active project';
  if (proj && state.selectedLocationId) scope += ` › ${locationName(proj, state.selectedLocationId)}`;
  document.getElementById('report-scope').innerHTML = `Reporting on <b>${escHtml(scope)}</b>.`;

  // Worksite dropdown: company lines with worksites only; seeded from the current view.
  const wsGroup = document.getElementById('wiz-worksite-group');
  const wsSel = document.getElementById('wiz-worksite');
  const locs = (proj && proj.locations) || [];
  if (locs.length) {
    wsSel.innerHTML = '<option value="">Whole line (all worksites)</option>'
      + locs.map(l => `<option value="${escHtml(l.id)}">${escHtml(l.name)}</option>`).join('');
    wsSel.value = state.selectedLocationId || '';
    wsGroup.classList.remove('hidden');
  } else {
    wsSel.innerHTML = '<option value="">Whole line (all worksites)</option>';
    wsSel.value = '';
    wsGroup.classList.add('hidden');
  }

  // Switches/derails/itemize apply to company lines only.
  document.getElementById('wiz-company-checks').classList.toggle('hidden', !isCompany);
  document.getElementById('wiz-itemize-row').classList.toggle('hidden', !isCompany);
  document.getElementById('wiz-itemize-hint').classList.toggle('hidden', !isCompany);
  document.getElementById('wiz-switches').checked = isCompany;
  document.getElementById('wiz-derails').checked = isCompany;
  document.getElementById('wiz-itemize').checked = false;

  document.getElementById('wiz-ties').value = 'both';
  document.getElementById('wiz-charts').checked = true;
  document.getElementById('wiz-downtime').checked = true;
  document.getElementById('wiz-period-mode').value = 'week';
  document.getElementById('wiz-week').value = '';
  document.getElementById('wiz-from').value = '';
  document.getElementById('wiz-to').value = '';

  clearMsg('report-msg');
  // The email stays blank by default: reports usually go to someone else (the boss, the office).

  wizSyncConditional();
  document.getElementById('report-modal').classList.remove('hidden');
  schedulePreview(0);
}

export function closeReportModal() {
  document.getElementById('report-modal').classList.add('hidden');
  clearMsg('report-msg');
}

/* Reveal the period date inputs for the chosen mode; downtime is line-level, so a single
   worksite disables it. */
export function wizSyncConditional() {
  const mode = document.getElementById('wiz-period-mode').value;
  document.getElementById('wiz-week-group').classList.toggle('hidden', mode !== 'pick');
  document.getElementById('wiz-range-group').classList.toggle('hidden', mode !== 'range');

  const worksite = document.getElementById('wiz-worksite').value;
  const dtRow = document.getElementById('wiz-downtime-row');
  const dt = document.getElementById('wiz-downtime');
  if (worksite) {
    dt.checked = false; dt.disabled = true; dtRow.classList.add('wiz-disabled');
  } else {
    dt.disabled = false; dtRow.classList.remove('wiz-disabled');
  }
}

export function readWizardOptions() {
  const isCompany = !!(state.project && state.project.project.kind === 'company');
  return {
    ties_mode: document.getElementById('wiz-ties').value,
    entity_detail: document.getElementById('wiz-itemize').checked ? 'itemized' : 'summary',
    switches: isCompany && document.getElementById('wiz-switches').checked,
    derails: isCompany && document.getElementById('wiz-derails').checked,
    downtime: document.getElementById('wiz-downtime').checked,
    charts: document.getElementById('wiz-charts').checked,
  };
}

export function readWizardPeriod() {
  const mode = document.getElementById('wiz-period-mode').value;
  if (mode === 'pick') return { mode: 'week', week: document.getElementById('wiz-week').value || null };
  if (mode === 'full') return { mode: 'full' };
  if (mode === 'range') return { mode: 'range',
    start: document.getElementById('wiz-from').value || null,
    end: document.getElementById('wiz-to').value || null };
  return { mode: 'week' };
}

export function reportPayload(email) {
  const payload = { email, options: readWizardOptions(), period: readWizardPeriod() };
  if (state.project) payload.project_id = state.project.project.id;
  const worksite = document.getElementById('wiz-worksite').value;
  if (worksite) payload.location = worksite;
  return payload;
}

/* Live preview: debounced. Re-render the report to HTML (no PDF) and show it scaled in an
   iframe, using the SAME scope/options/period payload as Send. */
let _previewTimer = null;
let _previewSeq = 0;

export function schedulePreview(delay) {
  if (document.getElementById('report-modal').classList.contains('hidden')) return;
  clearTimeout(_previewTimer);
  _previewTimer = setTimeout(runPreview, delay == null ? 450 : delay);
}

async function runPreview() {
  const pane = document.getElementById('wiz-preview-body');
  if (pane.offsetParent === null) return;            // preview hidden (mobile): skip
  if (!state.project) {
    pane.innerHTML = '<p class="wiz-preview-empty">Select a project to preview.</p>';
    return;
  }
  const seq = ++_previewSeq;
  const payload = reportPayload(null);
  delete payload.email;
  let res;
  try {
    res = await api('POST', '/api/reports/preview', payload);
  } catch {
    return;                                          // network blip: keep the last preview
  }
  if (!res || seq !== _previewSeq) return;           // superseded by a newer request or auth redirect
  if (!res.ok) {
    pane.innerHTML = '<p class="wiz-preview-empty">No preview available for this selection.</p>';
    return;
  }
  renderPreview(await res.text());
}

function renderPreview(html) {
  const pane = document.getElementById('wiz-preview-body');
  pane.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.className = 'wiz-preview-frame-wrap';
  const iframe = document.createElement('iframe');
  iframe.setAttribute('title', 'Report preview');
  iframe.setAttribute('scrolling', 'no');
  wrap.appendChild(iframe);
  pane.appendChild(wrap);
  const fit = () => scalePreview(iframe, wrap, pane);
  iframe.addEventListener('load', fit);
  iframe.srcdoc = html;
  setTimeout(fit, 80);                               // in case load already fired
}

function scalePreview(iframe, wrap, pane) {
  const PAGE_W = 816;                                // 8.5in at 96dpi
  const avail = pane.clientWidth - 48;               // minus body padding (24px each side)
  const scale = Math.max(0.2, Math.min(1, avail / PAGE_W));
  let docH = 1056;                                   // 11in fallback
  try {
    const d = iframe.contentDocument;
    if (d && d.body) docH = Math.max(d.body.scrollHeight, d.documentElement.scrollHeight, 400);
  } catch (e) { /* srcdoc is same-origin; ignore */ }
  iframe.style.width = PAGE_W + 'px';
  iframe.style.height = docH + 'px';
  iframe.style.transform = `scale(${scale})`;
  iframe.style.transformOrigin = 'top left';
  wrap.style.width = (PAGE_W * scale) + 'px';
  wrap.style.height = (docH * scale) + 'px';
  wrap.style.margin = '0 auto';
}

export async function handleReportSubmit(e) {
  e.preventDefault();
  const email = document.getElementById('report-email').value.trim();
  const msgEl = document.getElementById('report-msg');
  const btn   = document.getElementById('report-submit');
  if (!email) { showMsg(msgEl, 'Enter an email address.', 'error'); return; }

  const reset = () => { btn.disabled = false; btn.textContent = 'Generate & Send'; };
  btn.disabled = true;
  btn.textContent = 'Generating...';
  showMsg(msgEl, 'Building the report and emailing it. This can take a few seconds...', 'success');

  let res;
  try {
    res = await api('POST', '/api/reports/send', reportPayload(email));
  } catch {
    showMsg(msgEl, 'Network error. Please try again.', 'error');
    reset();
    return;
  }
  if (!res) { closeReportModal(); return; }   // 401: the sign-in screen is showing

  const data = await res.json().catch(() => ({}));
  if (res.ok) {
    const where = data.worksite ? ` · ${data.worksite}` : '';
    showMsg(msgEl, `Sent to ${data.email}${where} (${data.week_label}).`, 'success');
    btn.textContent = 'Sent ✓';
    setTimeout(closeReportModal, 2400);
    return;
  }
  let detail = data.detail;
  if (Array.isArray(detail)) detail = 'Please enter a valid email address.';
  showMsg(msgEl, detail || 'Could not send the report. Please try again.', 'error');
  reset();
}

/* Reflect the current scope on the Generate Report button so it is obvious the report follows
   the sidebar selection: a worksite shows its name, a whole company line shows "Full line". */
export function updateReportButton() {
  const scopeEl = document.getElementById('report-btn-scope');
  if (!scopeEl) return;
  let scope = '';
  if (state.project) {
    if (state.selectedLocationId) scope = locationName(state.project, state.selectedLocationId);
    else if (state.project.project.kind === 'company') scope = 'Full line';
  }
  scopeEl.textContent = scope ? ` · ${scope}` : '';
  document.getElementById('generate-report-btn').title =
    scope ? `Generate a report for ${scope}` : 'Generate a report';
}
