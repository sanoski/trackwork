/* The sidebar (lines, worksites) and loading the selected project into the dashboard. */
import { state } from './state.js';
import { api } from './api.js';
import { escHtml, showView, todayStr, locationName } from './util.js';
import { renderDashboard } from './dashboard.js';
import { updateReportButton } from './reports.js';

export async function loadProjectList() {
  const res = await api('GET', '/api/projects');
  if (!res) return;                       // 401: the API layer already raised the sign-in screen
  if (res.ok) {
    state.projects = await res.json();
    renderProjectList();
  }
}

export function renderProjectList() {
  const container = document.getElementById('project-list');
  container.innerHTML = '';

  const active   = state.projects.filter(p => p.status === 'active');
  const complete = state.projects.filter(p => p.status === 'complete');
  const archived = state.projects.filter(p => p.status === 'archived');

  function makeItem(p) {
    const dot = p.status === 'active' ? 'dot-active'
              : p.status === 'complete' ? 'dot-complete'
              : 'dot-archived';
    const isCurrent = state.project && state.project.project.id === p.id;
    const isTree = p.kind === 'company' && Array.isArray(p.locations) && p.locations.length > 0;

    const lineBtn = document.createElement('button');
    lineBtn.className = 'project-item';
    lineBtn.dataset.id = p.id;
    // The line (parent) is "active" only when its whole-line view is showing.
    if (isCurrent && !state.selectedLocationId) lineBtn.classList.add('active');

    if (!isTree) {
      lineBtn.innerHTML = `<span class="project-dot ${dot}"></span><span>${escHtml(p.name)}</span>`;
      lineBtn.addEventListener('click', () => selectFromSidebar(p.id, null));
      return lineBtn;
    }

    // Company line with worksites: a parent row + indented location children.
    const expanded = state.expanded.has(p.id);
    lineBtn.classList.add('has-children');
    lineBtn.innerHTML = `
      <span class="tree-caret${expanded ? ' open' : ''}">&#9656;</span>
      <span class="project-dot ${dot}"></span>
      <span>${escHtml(p.name)}</span>`;
    lineBtn.addEventListener('click', (ev) => {
      if (ev.target.closest('.tree-caret')) { toggleExpanded(p.id); return; }  // caret toggles; label selects
      selectFromSidebar(p.id, null);
    });

    const group = document.createElement('div');
    group.className = 'project-group';
    group.appendChild(lineBtn);

    const childWrap = document.createElement('div');
    childWrap.className = 'project-children';
    if (!expanded) childWrap.classList.add('hidden');
    p.locations.forEach(loc => {
      const cb = document.createElement('button');
      cb.className = 'project-item project-child';
      cb.dataset.id = p.id;
      cb.dataset.loc = loc.id;
      if (isCurrent && state.selectedLocationId === loc.id) cb.classList.add('active');
      cb.innerHTML = `<span class="child-tick"></span><span>${escHtml(loc.name)}</span>`;
      cb.addEventListener('click', () => selectFromSidebar(p.id, loc.id));
      childWrap.appendChild(cb);
    });
    group.appendChild(childWrap);
    return group;
  }

  function section(label, items) {
    if (items.length === 0) return;
    const lbl = document.createElement('div');
    lbl.className = 'project-section-label';
    lbl.textContent = label;
    container.appendChild(lbl);
    items.forEach(p => container.appendChild(makeItem(p)));
  }

  section('Active', active);
  section('Completed', complete);
  section('Archived', archived);

  if (state.projects.length === 0) {
    const p = document.createElement('p');
    p.className = 'text-muted text-sm';
    p.style.padding = '0.5rem';
    p.textContent = 'No projects found.';
    container.appendChild(p);
  }
}

export function selectFromSidebar(id, locId) {
  state.expanded.add(id);   // selecting a line (or a worksite under it) opens its tree
  loadProject(id, locId);
  if (window.innerWidth <= 768) document.body.classList.add('sidebar-collapsed');
}

export function toggleExpanded(id) {
  if (state.expanded.has(id)) state.expanded.delete(id);
  else state.expanded.add(id);
  renderProjectList();   // selection unchanged; just redraw the tree
}

export async function loadProject(id, locId = null) {
  showView('loading-state');
  const res = await api('GET', `/api/projects/${id}`);
  if (!res || !res.ok) { showView('empty-state'); return; }

  state.project = await res.json();           // always the whole line
  state.selectedLocationId = locId;
  state.expanded.add(id);

  // A worksite child shows a filtered view; the line shows the full aggregate.
  const view = locId ? filterProjectByLocation(state.project, locId) : state.project;
  renderDashboard(view);
  renderProjectList();   // rebuild sidebar so active/expanded states are correct

  const locName = locId ? locationName(state.project, locId) : null;
  document.getElementById('project-title').textContent =
    locName ? `${state.project.project.name} › ${locName}` : state.project.project.name;
  updateReportButton();

  const dateEl = document.getElementById('count-date');
  if (dateEl) dateEl.value = todayStr();
}

/* A location-scoped view of a company line: same project meta, but daily log / switches /
   derails filtered to one worksite, with a location-scoped running total. Equipment downtime
   is a line-level log, so it is omitted from a worksite view. */
export function filterProjectByLocation(project, locId) {
  const meta = project.project;
  const days = (project.daily_log || [])
    .filter(e => e.location === locId)
    .map(e => ({ ...e }))   // copy: we recompute running_total without touching the originals
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  let running = 0;
  days.forEach(e => {
    running += e.ties;
    e.running_total = running;
    e.remaining = meta.goal_ties != null ? meta.goal_ties - running : null;
  });
  return {
    project: meta,
    locations: project.locations,
    daily_log: days,
    switches: (project.switches || []).filter(s => s.location === locId),
    derails: (project.derails || []).filter(d => d.location === locId),
    equipment_downtime: [],
  };
}

export async function refreshProject() {
  if (!state.project) return;
  const res = await api('GET', `/api/projects/${state.project.project.id}`);
  if (res && res.ok) {
    state.project = await res.json();
    const view = state.selectedLocationId
      ? filterProjectByLocation(state.project, state.selectedLocationId)
      : state.project;
    renderDashboard(view);
  }
}
