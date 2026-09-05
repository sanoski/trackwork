/* Equipment downtime: the incident rows inside the Log Work screen, their submission, and the
   Edit Downtime screen (change times or notes, or delete an entry). */
import { state } from './state.js';
import { api, errorDetail } from './api.js';
import { showMsg, escHtml, todayStr, formatDate } from './util.js';
import { refreshProject } from './projects.js';
import { openScreen, closeScreen } from './panel.js';

export function renderIncidentSection() {
  return `
    <section class="form-section" id="incident-section">
      <h4>Equipment downtime <span class="text-muted">(optional)</span></h4>
      <p class="text-muted text-sm">Log one or more machines for the date above. Submit them all at once.</p>
      <div id="incident-rows"></div>
      <button id="add-incident-btn" class="btn-ghost btn-sm" type="button">+ Add Another Machine</button>
      <p id="downtime-msg" class="msg hidden"></p>
      <button id="submit-downtime-btn" class="btn-primary" type="button">Submit Downtime</button>
    </section>`;
}

export function wireIncidentSection(body) {
  body.querySelector('#add-incident-btn').addEventListener('click', addIncidentRow);
  body.querySelector('#submit-downtime-btn').addEventListener('click', handleDowntimeSubmit);
  resetIncidents();
}

export function resetIncidents() {
  const container = document.getElementById('incident-rows');
  if (!container) return;
  container.innerHTML = '';
  addIncidentRow();
}

export function addIncidentRow() {
  const container = document.getElementById('incident-rows');
  const idx = container.children.length;

  const div = document.createElement('div');
  div.className = 'incident-row';
  div.innerHTML = `
    <div class="incident-row-header">
      <span>Machine ${idx + 1}</span>
      ${idx > 0 ? `<button class="remove-incident-btn" type="button" title="Remove">&times;</button>` : ''}
    </div>
    <div class="form-group">
      <label>Machine</label>
      <select class="incident-machine">
        ${state.equipment.map(e => `<option value="${escHtml(e)}">${escHtml(e)}</option>`).join('')}
      </select>
    </div>
    <div class="time-row">
      <div class="form-group">
        <label>Time Down (HH:MM)</label>
        <input type="time" class="incident-down-at">
      </div>
      <div class="form-group">
        <label>Back in Service (HH:MM)</label>
        <input type="time" class="incident-resumed">
      </div>
    </div>
    <div class="form-group">
      <label>Notes</label>
      <textarea class="incident-notes" placeholder="Optional: describe the issue"></textarea>
    </div>
  `;

  const removeBtn = div.querySelector('.remove-incident-btn');
  if (removeBtn) removeBtn.addEventListener('click', () => div.remove());

  container.appendChild(div);
}

export async function handleDowntimeSubmit() {
  if (!state.project) return;

  const rows    = document.querySelectorAll('#incident-rows .incident-row');
  const msgEl   = document.getElementById('downtime-msg');
  const btn     = document.getElementById('submit-downtime-btn');
  const dateEl  = document.getElementById('log-date');
  const date    = (dateEl && dateEl.value) || todayStr();   // the date chosen on the log form
  const incidents = [];

  for (const row of rows) {
    const machine  = row.querySelector('.incident-machine').value;
    const downAt   = row.querySelector('.incident-down-at').value   || null;
    const resumed  = row.querySelector('.incident-resumed').value   || null;
    const notes    = row.querySelector('.incident-notes').value.trim() || null;
    if (!machine) { showMsg(msgEl, 'Select a machine for each row.', 'error'); return; }
    incidents.push({ date, machine, down_at: downAt, resumed, notes });
  }

  if (!incidents.length) {
    showMsg(msgEl, 'Add at least one downtime incident.', 'error');
    return;
  }

  btn.disabled = true; btn.textContent = 'Saving...';
  const res = await api('POST', `/api/projects/${state.project.project.id}/downtime`, { incidents });
  btn.disabled = false; btn.textContent = 'Submit Downtime';

  if (!res) return;
  if (!res.ok) {
    showMsg(msgEl, await errorDetail(res, 'Submit failed. Please try again.'), 'error');
    return;
  }

  const added = await res.json();
  showMsg(msgEl, `Saved: ${added.length} downtime incident${added.length !== 1 ? 's' : ''} logged for ${formatDate(date)}.`, 'success');
  resetIncidents();
  await refreshProject();
}

export async function loadEquipment() {
  const res = await api('GET', '/api/equipment');
  if (res && res.ok) {
    const data = await res.json();
    state.equipment = data.equipment || [];
  } else {
    state.equipment = ['Tie Inserter', 'Broom', 'Plate Setter', 'Tamper', 'Spiker/Gauger', 'Other'];
  }
}

/* Edit or delete one downtime entry. The machine is the entry's key and cannot be changed;
   an empty time field leaves that time as it was. */
export function openEditDowntime(date, machine, downAt) {
  const entry = ((state.project && state.project.equipment_downtime) || [])
    .find(d => d.date === date && d.machine === machine && (downAt ? d.down_at === downAt : true));
  if (!entry) return;
  const body = openScreen('Edit Downtime', `
    <p class="panel-intro"><b>${escHtml(entry.machine)}</b> on ${formatDate(entry.date)}.</p>
    <form id="dt-form" novalidate>
      <div class="form-row">
        <div class="form-group"><label for="dt-down-at">Time down</label><input type="time" id="dt-down-at" value="${entry.down_at || ''}"></div>
        <div class="form-group"><label for="dt-resumed">Back in service</label><input type="time" id="dt-resumed" value="${entry.resumed || ''}"></div>
      </div>
      <div class="form-group"><label for="dt-notes">Notes</label><textarea id="dt-notes">${escHtml(entry.notes || '')}</textarea></div>
      <p id="dt-msg" class="msg hidden"></p>
      <div class="panel-actions">
        <button type="submit" id="dt-save" class="btn-primary btn-big">Save</button>
        <button type="button" id="dt-delete" class="btn-danger">Delete</button>
        <button type="button" id="dt-cancel" class="btn-ghost">Cancel</button>
      </div>
    </form>`);
  const pid = state.project.project.id;
  body.querySelector('#dt-cancel').addEventListener('click', closeScreen);
  body.querySelector('#dt-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById('dt-msg');
    const payload = { machine: entry.machine, notes: document.getElementById('dt-notes').value.trim() };
    if (entry.down_at) payload.match_down_at = entry.down_at;
    const downAtVal = document.getElementById('dt-down-at').value;
    const resumedVal = document.getElementById('dt-resumed').value;
    if (downAtVal && downAtVal !== entry.down_at) payload.down_at = downAtVal;
    if (resumedVal && resumedVal !== entry.resumed) payload.resumed = resumedVal;
    const btn = document.getElementById('dt-save');
    btn.disabled = true; btn.textContent = 'Saving...';
    const res = await api('PATCH', `/api/projects/${pid}/downtime/${entry.date}`, payload);
    btn.disabled = false; btn.textContent = 'Save';
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not save.'), 'error'); return; }
    await refreshProject();
    closeScreen();
  });
  body.querySelector('#dt-delete').addEventListener('click', async () => {
    if (!confirm(`Delete this downtime entry for ${entry.machine} on ${formatDate(entry.date)}?`)) return;
    const params = new URLSearchParams({ machine: entry.machine });
    if (entry.down_at) params.set('down_at', entry.down_at);
    const res = await api('DELETE', `/api/projects/${pid}/downtime/${entry.date}?${params}`);
    if (!res) return;
    if (!res.ok) { showMsg(document.getElementById('dt-msg'), await errorDetail(res, 'Could not delete.'), 'error'); return; }
    await refreshProject();
    closeScreen();
  });
}
