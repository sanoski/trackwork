/* Switches, derails, and worksites: the list screen, the add/edit form with timber rows, and
   worksite management. Same service paths MCP and the CLI use. Loaded on demand. */
import { state } from './state.js';
import { api, errorDetail } from './api.js';
import { escHtml, showMsg, formatDate, todayStr } from './util.js';
import { refreshProject, loadProjectList } from './projects.js';
import { openScreen } from './panel.js';
import { entityTotals } from './dashboard.js';
import { locationOptions } from './entry.js';

const KIND = {
  switch: { label: 'Switch', path: 'switches', list: p => p.switches || [] },
  derail: { label: 'Derail', path: 'derails',  list: p => p.derails  || [] },
};

function locName(project, id) {
  const l = (project.locations || []).find(x => x.id === id);
  return l ? l.name : id;
}

export function openStructuresScreen() {
  const p = state.project;
  if (!p) return;
  const row = (kind, e) => {
    const [pl, ac] = entityTotals(e);
    const bits = [formatDate(e.date), `planned ${pl} / actual ${ac}`];
    if (e.location) bits.push(escHtml(locName(p, e.location)));
    if (e.derail_type) bits.push(escHtml(e.derail_type));
    return `
      <div class="list-row">
        <div class="list-main">
          <div class="list-title">${escHtml(e.name)}</div>
          <div class="list-sub">${bits.join(' · ')}</div>
        </div>
        <div class="list-actions"><button type="button" class="row-act" data-kind="${kind}" data-id="${escHtml(e.id)}">Edit</button></div>
      </div>`;
  };
  const sw = KIND.switch.list(p), dr = KIND.derail.list(p);
  const body = openScreen('Switches & Derails', `
    <p class="panel-intro">Each switch or derail is a dated record with its timber rows (planned and actual, by length). Edit one, or add a new one.</p>
    <div class="panel-actions">
      <button type="button" class="btn-primary" data-add="switch">+ Add Switch</button>
      <button type="button" class="btn-primary" data-add="derail">+ Add Derail</button>
    </div>
    <h4 style="margin-top:1.25rem">Switches <span class="count-pill">${sw.length}</span></h4>
    ${sw.length ? sw.map(e => row('switch', e)).join('') : '<p class="text-muted text-sm">None yet.</p>'}
    <h4 style="margin-top:1.25rem">Derails <span class="count-pill">${dr.length}</span></h4>
    ${dr.length ? dr.map(e => row('derail', e)).join('') : '<p class="text-muted text-sm">None yet.</p>'}
  `);
  body.querySelectorAll('[data-add]').forEach(b =>
    b.addEventListener('click', () => openStructureForm(b.dataset.add, null)));
  body.querySelectorAll('.row-act[data-kind]').forEach(b => b.addEventListener('click', () => {
    const e = KIND[b.dataset.kind].list(p).find(x => x.id === b.dataset.id);
    if (e) openStructureForm(b.dataset.kind, e);
  }));
}

/* Add (entity null) or edit a switch or derail. `timbers` always replaces the whole list. */
export function openStructureForm(kind, entity) {
  const K = KIND[kind];
  const p = state.project;
  if (!K || !p) return;
  const isEdit = !!entity;
  const timbers = isEdit ? entity.timbers : [{ length: 9, planned: 0, actual: 0, head_block: false }];
  const locs = p.locations || [];
  const typeField = kind === 'derail' ? `
        <div class="form-group"><label for="st-type">Type</label>
          <select id="st-type"><option value="">Not set</option>${
            ['stationary', 'portable', 'switch'].map(t =>
              `<option value="${t}"${isEdit && entity.derail_type === t ? ' selected' : ''}>${t}</option>`).join('')
          }</select></div>` : '';
  const body = openScreen(`${isEdit ? 'Edit' : 'Add'} ${K.label}`, `
    <form id="st-form" novalidate>
      <div class="form-group"><label for="st-name">Name</label>
        <input type="text" id="st-name" maxlength="100" value="${escHtml(isEdit ? entity.name : '')}"
               placeholder="${kind === 'switch' ? 'e.g. North Main Switch' : 'e.g. South Derail Head Blocks'}" required></div>
      <div class="form-row">
        <div class="form-group"><label for="st-date">Date completed</label>
          <input type="date" id="st-date" value="${isEdit ? entity.date : todayStr()}"${isEdit ? ' disabled' : ' required'}></div>
        ${typeField}
      </div>
      ${locs.length ? `<div class="form-group"><label for="st-location">Worksite</label>
        <select id="st-location">${locationOptions(isEdit ? entity.location : state.selectedLocationId)}</select></div>` : ''}
      <h4>Timbers by length</h4>
      <div class="timber-head"><span>Length (ft)</span><span>Planned</span><span>Actual</span><span>HB</span><span></span></div>
      <div class="timber-rows" id="timber-rows"></div>
      <button type="button" id="add-timber-btn" class="btn-ghost btn-sm">+ Add Length</button>
      <div class="form-group" style="margin-top:1rem"><label for="st-notes">Notes <span class="text-muted">(optional)</span></label>
        <textarea id="st-notes">${escHtml(isEdit ? (entity.notes || '') : '')}</textarea></div>
      <p id="st-msg" class="msg hidden"></p>
      <div class="panel-actions">
        <button type="submit" id="st-submit" class="btn-primary btn-big">${isEdit ? 'Save Changes' : `Add ${K.label}`}</button>
        ${isEdit ? '<button type="button" id="st-delete" class="btn-danger">Delete</button>' : ''}
        <button type="button" id="st-back" class="btn-ghost">Back</button>
      </div>
    </form>`);

  const rows = body.querySelector('#timber-rows');
  const addRow = (t = { length: '', planned: 0, actual: 0, head_block: false }) => {
    const div = document.createElement('div');
    div.className = 'timber-row';
    div.innerHTML = `
      <input type="number" class="tb-len" inputmode="numeric" min="1" max="40" placeholder="ft" value="${t.length === '' ? '' : t.length}">
      <input type="number" class="tb-planned" inputmode="numeric" min="0" value="${t.planned}">
      <input type="number" class="tb-actual" inputmode="numeric" min="0" value="${t.actual}">
      <label class="hb"><input type="checkbox" class="tb-hb"${t.head_block ? ' checked' : ''}> HB</label>
      <button type="button" class="row-act danger tb-remove" title="Remove this length">&times;</button>`;
    div.querySelector('.tb-remove').addEventListener('click', () => div.remove());
    rows.appendChild(div);
  };
  timbers.forEach(t => addRow(t));
  body.querySelector('#add-timber-btn').addEventListener('click', () => addRow());
  body.querySelector('#st-back').addEventListener('click', openStructuresScreen);

  const readTimbers = () => [...rows.querySelectorAll('.timber-row')].map(r => ({
    length: parseInt(r.querySelector('.tb-len').value, 10),
    planned: parseInt(r.querySelector('.tb-planned').value || '0', 10),
    actual: parseInt(r.querySelector('.tb-actual').value || '0', 10),
    head_block: r.querySelector('.tb-hb').checked,
  }));

  body.querySelector('#st-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById('st-msg');
    const name = document.getElementById('st-name').value.trim();
    if (!name) { showMsg(msgEl, 'Enter a name.', 'error'); return; }
    const tb = readTimbers();
    if (tb.some(t => isNaN(t.length) || t.length < 1)) { showMsg(msgEl, 'Every timber row needs a length in feet.', 'error'); return; }
    if (kind === 'switch' && !tb.length) { showMsg(msgEl, 'A switch needs at least one timber row.', 'error'); return; }
    const locSel = document.getElementById('st-location');
    const typeSel = document.getElementById('st-type');
    const notes = document.getElementById('st-notes').value.trim();
    let method, url, payload;
    if (isEdit) {
      payload = { new_name: name, timbers: tb, notes };
      if (locSel) payload.location = locSel.value;
      if (typeSel) payload.derail_type = typeSel.value;
      method = 'PATCH'; url = `/api/projects/${p.project.id}/${K.path}/${entity.id}`;
    } else {
      const date = document.getElementById('st-date').value;
      if (!date) { showMsg(msgEl, 'Pick the date completed.', 'error'); return; }
      payload = { name, date, timbers: tb, notes: notes || null };
      if (locSel && locSel.value) payload.location = locSel.value;
      if (typeSel && typeSel.value) payload.derail_type = typeSel.value;
      method = 'POST'; url = `/api/projects/${p.project.id}/${K.path}`;
    }
    const btn = document.getElementById('st-submit');
    const label = btn.textContent;
    btn.disabled = true; btn.textContent = 'Saving...';
    const res = await api(method, url, payload);
    btn.disabled = false; btn.textContent = label;
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not save.'), 'error'); return; }
    await refreshProject();
    openStructuresScreen();
  });

  const del = body.querySelector('#st-delete');
  if (del) del.addEventListener('click', async () => {
    if (!confirm(`Delete ${K.label.toLowerCase()} "${entity.name}"? This cannot be undone.`)) return;
    const res = await api('DELETE', `/api/projects/${p.project.id}/${K.path}/${entity.id}`);
    if (!res) return;
    if (!res.ok) { showMsg(document.getElementById('st-msg'), await errorDetail(res, 'Could not delete.'), 'error'); return; }
    await refreshProject();
    openStructuresScreen();
  });
}

/* Worksites (locations) on a company line: add, rename (the id stays stable), delete (refused
   while any work still references it). */
export function openWorksitesScreen() {
  const p = state.project;
  if (!p) return;
  if (p.project.kind !== 'company') {
    openScreen('Worksites', '<p class="panel-intro">Worksites belong to company lines. Sponsored jobs do not have them.</p>');
    return;
  }
  const locs = p.locations || [];
  const refs = loc => ({
    days: (p.daily_log || []).filter(e => e.location === loc.id).length,
    sw: (p.switches || []).filter(s => s.location === loc.id).length,
    dr: (p.derails || []).filter(d => d.location === loc.id).length,
  });
  const body = openScreen('Worksites', `
    <p class="panel-intro">Worksites are the places on <b>${escHtml(p.project.name)}</b> where work gets tagged (a town, a yard, a siding). Renaming keeps the work attached. A worksite can only be deleted once nothing references it.</p>
    <form id="ws-form" novalidate>
      <div class="form-group"><label for="ws-name">New worksite</label><input type="text" id="ws-name" maxlength="80" placeholder="e.g. St. Johnsbury"></div>
      <p id="ws-msg" class="msg hidden"></p>
      <button type="submit" class="btn-primary">+ Add Worksite</button>
    </form>
    <h4 style="margin-top:1.25rem">Existing <span class="count-pill">${locs.length}</span></h4>
    ${locs.length ? locs.map(l => { const r = refs(l); return `
      <div class="list-row">
        <div class="list-main">
          <div class="list-title">${escHtml(l.name)}</div>
          <div class="list-sub">${r.days} tie day${r.days === 1 ? '' : 's'} · ${r.sw} switch${r.sw === 1 ? '' : 'es'} · ${r.dr} derail${r.dr === 1 ? '' : 's'}</div>
        </div>
        <div class="list-actions">
          <button type="button" class="row-act" data-rename="${escHtml(l.id)}">Rename</button>
          <button type="button" class="row-act danger" data-delete="${escHtml(l.id)}">Delete</button>
        </div>
      </div>`; }).join('') : '<p class="text-muted text-sm">No worksites yet.</p>'}
  `);
  const pid = p.project.id;
  const after = async () => { await refreshProject(); await loadProjectList(); openWorksitesScreen(); };

  body.querySelector('#ws-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById('ws-msg');
    const name = document.getElementById('ws-name').value.trim();
    if (!name) { showMsg(msgEl, 'Enter a name.', 'error'); return; }
    const res = await api('POST', `/api/projects/${pid}/locations`, { name });
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not add.'), 'error'); return; }
    await after();
  });
  body.querySelectorAll('[data-rename]').forEach(b => b.addEventListener('click', async () => {
    const loc = locs.find(l => l.id === b.dataset.rename);
    const name = prompt('New name for this worksite:', loc ? loc.name : '');
    if (!name || !name.trim()) return;
    const res = await api('PATCH', `/api/projects/${pid}/locations/${b.dataset.rename}`, { new_name: name.trim() });
    if (!res) return;
    if (!res.ok) { alert(await errorDetail(res, 'Could not rename.')); return; }
    await after();
  }));
  body.querySelectorAll('[data-delete]').forEach(b => b.addEventListener('click', async () => {
    const loc = locs.find(l => l.id === b.dataset.delete);
    if (!confirm(`Delete worksite "${loc ? loc.name : b.dataset.delete}"?`)) return;
    const res = await api('DELETE', `/api/projects/${pid}/locations/${b.dataset.delete}`);
    if (!res) return;
    if (!res.ok) { alert(await errorDetail(res, 'Could not delete.')); return; }
    await after();
  }));
}
