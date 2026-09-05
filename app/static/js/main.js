/* Entry point: wires the screens together. No business logic lives here. Editing screens that
   are not needed on every visit load on demand (dynamic import). */
import { state } from './state.js';
import { checkAuth, initAuth, handleLogin, handleLogout, showLoginModal } from './auth.js';
import { loadProjectList, loadProject } from './projects.js';
import { openReportModal, closeReportModal, handleReportSubmit, wizSyncConditional, schedulePreview } from './reports.js';
import { openHelpModal, closeHelpModal, setupHelpAudio } from './help.js';
import { openLogScreen, openEditDay } from './entry.js';
import { openEditDowntime } from './downtime.js';
import { closeScreen, isScreenOpen } from './panel.js';
import { showView } from './util.js';

document.addEventListener('DOMContentLoaded', init);

async function init() {
  bindStaticEvents();
  initAuth();
  await checkAuth();
  await loadProjectList();
  await openActiveProject();
}

async function openActiveProject() {
  if (state.projects.length > 0) {
    const active = state.projects.find(p => p.status === 'active') || state.projects[0];
    await loadProject(active.id);
  } else {
    showView('empty-state');
  }
}

const on = (id, event, fn) => document.getElementById(id).addEventListener(event, fn);

function bindStaticEvents() {
  // Sign-in and sign-out
  on('login-form', 'submit', handleLogin);
  on('header-login-btn', 'click', showLoginModal);
  on('logout-btn', 'click', handleLogout);
  document.addEventListener('auth:login', async () => {
    await loadProjectList();
    if (state.projects.length > 0 && !state.project) await openActiveProject();
  });
  document.addEventListener('auth:logout', () => { if (isScreenOpen()) closeScreen(); loadProjectList(); });

  // Generate Report wizard
  on('generate-report-btn', 'click', openReportModal);
  on('report-close', 'click', closeReportModal);
  on('report-form', 'submit', handleReportSubmit);
  on('report-form', 'change', () => { wizSyncConditional(); schedulePreview(); });
  ['wiz-week', 'wiz-from', 'wiz-to'].forEach(id => on(id, 'input', () => schedulePreview()));
  on('report-modal', 'click', (e) => { if (e.target.id === 'report-modal') closeReportModal(); });

  // Help & Guide
  on('help-btn', 'click', openHelpModal);
  on('help-close', 'click', closeHelpModal);
  setupHelpAudio();
  on('help-modal', 'click', (e) => { if (e.target.id === 'help-modal') closeHelpModal(); });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (!document.getElementById('report-modal').classList.contains('hidden')) closeReportModal();
    if (!document.getElementById('help-modal').classList.contains('hidden')) closeHelpModal();
    if (isScreenOpen()) closeScreen();
  });

  // Sidebar and the editing screens
  on('sidebar-toggle', 'click', () => document.body.classList.toggle('sidebar-collapsed'));
  on('log-data-btn', 'click', openLogScreen);
  on('nav-structures', 'click', async () => (await import('./structures.js')).openStructuresScreen());
  on('nav-worksites', 'click', async () => (await import('./structures.js')).openWorksitesScreen());
  on('nav-projects', 'click', async () => (await import('./projects_admin.js')).openProjectsScreen());
  on('nav-admin', 'click', async () => (await import('./admin.js')).openAdminScreen());
  on('close-panel-btn', 'click', closeScreen);
  on('panel-backdrop', 'click', closeScreen);

  // Row actions rendered inside the dashboard: correct a day, edit downtime, edit a switch/derail.
  on('dashboard', 'click', async (e) => {
    const btn = e.target.closest('.row-act[data-act]');
    if (!btn) return;
    const d = btn.dataset;
    if (d.act === 'edit-day') {
      openEditDay(d.date);
    } else if (d.act === 'edit-downtime') {
      openEditDowntime(d.date, d.machine, d.downAt || null);
    } else if (d.act === 'edit-structure') {
      const list = d.kind === 'switch' ? state.project.switches : state.project.derails;
      const entity = (list || []).find(x => x.id === d.id);
      if (entity) (await import('./structures.js')).openStructureForm(d.kind, entity);
    }
  });
}
