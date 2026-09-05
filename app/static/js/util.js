/* Small shared helpers: view switching, messages, dates, escaping. No app state, no fetch. */

export function showView(id) {
  ['loading-state', 'empty-state', 'dashboard'].forEach(v =>
    document.getElementById(v).classList.toggle('hidden', v !== id));
}

export function showMsg(el, text, type) {
  el.textContent = text;
  el.className = `msg msg-${type}`;
  el.classList.remove('hidden');
}

export function clearMsg(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = '';
  el.classList.add('hidden');
}

export function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

export function formatDate(str) {
  // "2026-05-11" becomes "May 11, 2026" (also accepts a Date object)
  const d = str instanceof Date ? str : new Date(str + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function shortDate(str) {
  // "2026-05-11" becomes "May 11"
  const d = new Date(str + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function formatDuration(minutes) {
  if (!minutes) return '-';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

export function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function locationName(project, locId) {
  const loc = (project.locations || []).find(l => l.id === locId);
  return loc ? loc.name : locId;
}
