/* Projects: set status (exactly one is active), edit the current project's details, and
   create a company line or a sponsored job. Admin only. Loaded on demand. */
import { state } from './state.js';
import { api, errorDetail } from './api.js';
import { escHtml, showMsg } from './util.js';
import { openScreen } from './panel.js';
import { loadProjectList, loadProject } from './projects.js';

const pill = s => `<span class="status-pill${s === 'active' ? ' active' : ''}">${s}</span>`;

export function openProjectsScreen() {
  const meta = state.project && state.project.project;
  const list = state.projects;
  const statusButtons = p => [
    p.status !== 'active'   ? `<button type="button" class="row-act" data-status="active" data-id="${escHtml(p.id)}">Make Active</button>` : '',
    p.status !== 'complete' ? `<button type="button" class="row-act" data-status="complete" data-id="${escHtml(p.id)}">Complete</button>` : '',
    p.status !== 'archived' ? `<button type="button" class="row-act danger" data-status="archived" data-id="${escHtml(p.id)}">Archive</button>` : '',
  ].join('');
  const body = openScreen('Projects', `
    <p class="panel-intro">Exactly one project is <b>active</b>: it opens by default and the weekly report covers it. Making another one active moves the current one to complete. Archived projects are hidden from the sidebar.</p>
    ${list.map(p => `
      <div class="list-row">
        <div class="list-main">
          <div class="list-title">${escHtml(p.name)} ${pill(p.status)}</div>
          <div class="list-sub">${escHtml(p.kind)} · ${escHtml(p.id)}</div>
        </div>
        <div class="list-actions">${statusButtons(p)}</div>
      </div>`).join('')}
    <p id="pj-msg" class="msg hidden"></p>
    ${meta ? `
    <hr class="section-divider">
    <h4>Edit ${escHtml(meta.name)}</h4>
    <form id="pj-edit" novalidate>
      <div class="form-group"><label for="pe-name">Name</label><input type="text" id="pe-name" value="${escHtml(meta.name)}" maxlength="100"></div>
      <div class="form-row">
        <div class="form-group"><label for="pe-target">Daily tie target</label><input type="number" id="pe-target" value="${meta.daily_target}" min="1"></div>
        <div class="form-group"><label for="pe-goal">Tie goal${meta.kind === 'company' ? ' <span class="text-muted">(usually none)</span>' : ''}</label><input type="number" id="pe-goal" value="${meta.goal_ties ?? ''}" min="1" placeholder="none"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label for="pe-deadline">Deadline</label><input type="date" id="pe-deadline" value="${meta.deadline || ''}"></div>
        <div class="form-group"><label for="pe-line">Line</label><input type="text" id="pe-line" value="${escHtml(meta.line || '')}" maxlength="100"></div>
      </div>
      <p id="pe-msg" class="msg hidden"></p>
      <button type="submit" class="btn-primary">Save Details</button>
    </form>` : ''}
    <hr class="section-divider">
    <h4>Create a project</h4>
    <form id="pj-create" novalidate>
      <div class="form-row">
        <div class="form-group"><label for="pc-kind">Kind</label>
          <select id="pc-kind">
            <option value="company">Company line (ongoing, in-house)</option>
            <option value="sponsored">Sponsored job (tie goal and deadline)</option>
          </select></div>
        <div class="form-group"><label for="pc-id">ID <span class="text-muted">(letters, numbers, - and _)</span></label><input type="text" id="pc-id" maxlength="50" placeholder="e.g. WACR_CRD or 942" required></div>
      </div>
      <div class="form-group"><label for="pc-name">Name</label><input type="text" id="pc-name" maxlength="100" placeholder="e.g. WACR Connecticut River Division" required></div>
      <div class="form-row">
        <div class="form-group"><label for="pc-line">Line <span class="text-muted">(company)</span></label><input type="text" id="pc-line" maxlength="100"></div>
        <div class="form-group"><label for="pc-target">Daily tie target</label><input type="number" id="pc-target" value="350" min="1"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label for="pc-goal">Tie goal <span class="text-muted">(sponsored)</span></label><input type="number" id="pc-goal" min="1"></div>
        <div class="form-group"><label for="pc-deadline">Deadline</label><input type="date" id="pc-deadline"></div>
      </div>
      <p id="pc-msg" class="msg hidden"></p>
      <button type="submit" class="btn-primary btn-big">Create Project</button>
    </form>`);

  const v = id => { const el = body.querySelector('#' + id); return el ? el.value.trim() : ''; };
  const intOrNull = id => { const x = parseInt(v(id), 10); return isNaN(x) ? null : x; };

  body.querySelectorAll('[data-status]').forEach(b => b.addEventListener('click', async () => {
    const msgEl = body.querySelector('#pj-msg');
    const res = await api('POST', `/api/projects/${b.dataset.id}/status`, { status: b.dataset.status });
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not change the status.'), 'error'); return; }
    await loadProjectList();
    if (state.project && state.project.project.id === b.dataset.id) await loadProject(b.dataset.id, state.selectedLocationId);
    openProjectsScreen();
  }));

  const edit = body.querySelector('#pj-edit');
  if (edit) edit.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msgEl = body.querySelector('#pe-msg');
    const payload = {};
    if (v('pe-name')) payload.name = v('pe-name');
    if (intOrNull('pe-target') !== null) payload.daily_target = intOrNull('pe-target');
    if (intOrNull('pe-goal') !== null) payload.goal_ties = intOrNull('pe-goal');
    if (v('pe-deadline')) payload.deadline = v('pe-deadline');
    if (v('pe-line')) payload.line = v('pe-line');
    if (!Object.keys(payload).length) { showMsg(msgEl, 'Nothing to save.', 'error'); return; }
    const res = await api('PATCH', `/api/projects/${meta.id}`, payload);
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not save.'), 'error'); return; }
    await loadProjectList();
    await loadProject(meta.id, state.selectedLocationId);
    openProjectsScreen();
  });

  body.querySelector('#pj-create').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msgEl = body.querySelector('#pc-msg');
    const payload = { id: v('pc-id'), name: v('pc-name'), kind: v('pc-kind'), daily_target: intOrNull('pc-target') || 350 };
    if (!payload.id || !payload.name) { showMsg(msgEl, 'An ID and a name are required.', 'error'); return; }
    if (v('pc-line')) payload.line = v('pc-line');
    if (intOrNull('pc-goal') !== null) payload.goal_ties = intOrNull('pc-goal');
    if (v('pc-deadline')) payload.deadline = v('pc-deadline');
    const res = await api('POST', '/api/projects', payload);
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not create the project.'), 'error'); return; }
    await loadProjectList();
    await loadProject(payload.id);
    openProjectsScreen();
  });
}
