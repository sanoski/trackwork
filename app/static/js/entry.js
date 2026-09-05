/* Logging ties: the "Log Work" screen (any date, new plus relay ties, worksite, track, and that
   day's machine downtime) and the "Correct a Day" screen. Same API paths MCP and the CLI use. */
import { state } from './state.js';
import { api, errorDetail } from './api.js';
import { todayStr, showMsg, escHtml, locationName, formatDate } from './util.js';
import { refreshProject } from './projects.js';
import { openScreen, closeScreen } from './panel.js';
import { renderIncidentSection, wireIncidentSection, loadEquipment } from './downtime.js';

export function locationOptions(selectedId) {
  const locs = (state.project && state.project.locations) || [];
  return '<option value="">Main line / unassigned</option>'
    + locs.map(l => `<option value="${escHtml(l.id)}"${l.id === selectedId ? ' selected' : ''}>${escHtml(l.name)}</option>`).join('');
}

function locationField(id, selectedId) {
  const locs = (state.project && state.project.locations) || [];
  if (!locs.length) return '';   // sponsored jobs and lines without worksites: ties go to the main line
  return `<div class="form-group"><label for="${id}">Worksite</label><select id="${id}">${locationOptions(selectedId)}</select></div>`;
}

function readCounts(tiesId, relayId, msgEl) {
  const ties = parseInt(document.getElementById(tiesId).value, 10);
  const relayRaw = document.getElementById(relayId).value.trim();
  const relay = relayRaw === '' ? 0 : parseInt(relayRaw, 10);
  if (isNaN(ties) || ties < 1) { showMsg(msgEl, 'Enter a valid tie count (1 or more).', 'error'); return null; }
  if (isNaN(relay) || relay < 0 || relay > ties) {
    showMsg(msgEl, 'Relay ties must be between 0 and the tie count (they are part of it, not extra).', 'error');
    return null;
  }
  return { ties, relay };
}

export async function openLogScreen() {
  if (!state.project) return;
  await loadEquipment();
  const body = openScreen('Log Work', `
    <p class="panel-intro">Logging to <b>${escHtml(state.project.project.name)}</b>. Pick the date, enter the ties, then add any machine downtime for that day.</p>
    <form id="log-form" novalidate>
      <h4>Ties installed</h4>
      <div class="form-row">
        <div class="form-group"><label for="log-date">Date</label><input type="date" id="log-date" value="${todayStr()}" required></div>
        <div class="form-group"><label for="log-ties">Ties installed</label><input type="number" id="log-ties" inputmode="numeric" min="1" max="10000" placeholder="e.g. 450" required></div>
      </div>
      <div class="form-group"><label for="log-relay">Of those, relay (reclaimed) ties <span class="text-muted">(optional)</span></label><input type="number" id="log-relay" inputmode="numeric" min="0" max="10000" placeholder="0"></div>
      ${locationField('log-location', state.selectedLocationId)}
      <div class="form-group"><label for="log-track">Track <span class="text-muted">(optional)</span></label><input type="text" id="log-track" maxlength="40" placeholder="e.g. Track 2; leave blank for main line"></div>
      <p id="log-msg" class="msg hidden"></p>
      <button type="submit" id="log-submit" class="btn-primary btn-big">Save Tie Count</button>
    </form>
    <hr class="section-divider">
    ${renderIncidentSection()}
  `);
  wireIncidentSection(body);
  body.querySelector('#log-form').addEventListener('submit', handleLogSubmit);
}

async function handleLogSubmit(e) {
  e.preventDefault();
  if (!state.project) return;
  const msgEl = document.getElementById('log-msg');
  const date = document.getElementById('log-date').value;
  if (!date) { showMsg(msgEl, 'Pick a date.', 'error'); return; }
  const counts = readCounts('log-ties', 'log-relay', msgEl);
  if (!counts) return;

  const payload = { date, ties: counts.ties, relay_ties: counts.relay };
  const track = document.getElementById('log-track').value.trim();
  const locSel = document.getElementById('log-location');
  if (track) payload.track = track;
  if (locSel && locSel.value) payload.location = locSel.value;

  const btn = document.getElementById('log-submit');
  btn.disabled = true; btn.textContent = 'Saving...';
  const res = await api('POST', `/api/projects/${state.project.project.id}/log`, payload);
  btn.disabled = false; btn.textContent = 'Save Tie Count';
  if (!res) return;
  if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not save. Please try again.'), 'error'); return; }

  const entry = await res.json();
  const where = entry.location ? ` at ${escHtml(locationName(state.project, entry.location))}` : '';
  showMsg(msgEl, `Saved: ${entry.ties.toLocaleString()} ties for ${entry.day}, ${formatDate(entry.date)}${where}. Running total ${entry.running_total.toLocaleString()}.`, 'success');
  document.getElementById('log-ties').value = '';
  document.getElementById('log-relay').value = '';
  document.getElementById('log-track').value = '';
  await refreshProject();
}

/* Correct an existing day (or one track of a split day). PATCH /log/{date}. */
export function openEditDay(dateStr) {
  const entry = ((state.project && state.project.daily_log) || []).find(e => e.date === dateStr);
  if (!entry) return;
  const tracks = entry.tracks || [];
  const first = tracks[0];
  const trackField = tracks.length
    ? `<div class="form-group"><label for="edit-track">Which track</label><select id="edit-track">${
        tracks.map(t => `<option value="${escHtml(t.track)}">${escHtml(t.track)} (${t.ties} ties, ${t.relay_ties} relay)</option>`).join('')
      }</select></div>`
    : '';
  const body = openScreen('Correct a Day', `
    <p class="panel-intro">Correcting <b>${escHtml(entry.day)}, ${formatDate(entry.date)}</b>. Every later running total is recalculated when you save.</p>
    <form id="edit-form" novalidate>
      ${trackField}
      <div class="form-row">
        <div class="form-group"><label for="edit-ties">Ties</label><input type="number" id="edit-ties" inputmode="numeric" min="1" max="10000" value="${first ? first.ties : entry.ties}" required></div>
        <div class="form-group"><label for="edit-relay">Relay ties</label><input type="number" id="edit-relay" inputmode="numeric" min="0" max="10000" value="${first ? first.relay_ties : (entry.relay_ties || 0)}"></div>
      </div>
      ${locationField('edit-location', entry.location)}
      <p id="edit-msg" class="msg hidden"></p>
      <div class="panel-actions">
        <button type="submit" id="edit-submit" class="btn-primary btn-big">Save Correction</button>
        <button type="button" id="edit-cancel" class="btn-ghost">Cancel</button>
      </div>
    </form>
  `);
  const trackSel = body.querySelector('#edit-track');
  if (trackSel) trackSel.addEventListener('change', () => {
    const t = tracks.find(x => x.track === trackSel.value);
    if (t) { body.querySelector('#edit-ties').value = t.ties; body.querySelector('#edit-relay').value = t.relay_ties; }
  });
  body.querySelector('#edit-cancel').addEventListener('click', closeScreen);
  body.querySelector('#edit-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById('edit-msg');
    const counts = readCounts('edit-ties', 'edit-relay', msgEl);
    if (!counts) return;
    const payload = { new_ties: counts.ties, relay_ties: counts.relay };
    if (trackSel) payload.track = trackSel.value;
    const locSel = document.getElementById('edit-location');
    if (locSel) payload.location = locSel.value;   // an empty value moves the day to the main line
    const btn = document.getElementById('edit-submit');
    btn.disabled = true; btn.textContent = 'Saving...';
    const res = await api('PATCH', `/api/projects/${state.project.project.id}/log/${entry.date}`, payload);
    btn.disabled = false; btn.textContent = 'Save Correction';
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not save. Please try again.'), 'error'); return; }
    const updated = await res.json();
    showMsg(msgEl, `Saved: ${updated.ties.toLocaleString()} ties on ${formatDate(updated.date)}. Running total ${updated.running_total.toLocaleString()}.`, 'success');
    await refreshProject();
  });
}
