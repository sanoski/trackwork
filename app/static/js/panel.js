/* The one side panel every editing screen renders into. A screen passes a title and its HTML,
   then wires its own listeners on the returned body element. */
let _closeTimer = null;

export function openScreen(title, html) {
  clearTimeout(_closeTimer);
  document.getElementById('panel-title').textContent = title;
  const body = document.getElementById('panel-body');
  body.innerHTML = html;
  body.scrollTop = 0;
  const panel = document.getElementById('side-panel');
  panel.classList.remove('hidden');
  requestAnimationFrame(() => panel.classList.add('open'));
  document.getElementById('panel-backdrop').classList.remove('hidden');
  const first = body.querySelector('input:not([readonly]):not([disabled]):not([type="hidden"]), select, textarea');
  if (first && window.innerWidth > 768) first.focus();   // no auto-keyboard on phones
  return body;
}

export function closeScreen() {
  const panel = document.getElementById('side-panel');
  panel.classList.remove('open');
  document.getElementById('panel-backdrop').classList.add('hidden');
  _closeTimer = setTimeout(() => panel.classList.add('hidden'), 210);   // after the slide-out
}

export function isScreenOpen() {
  return !document.getElementById('side-panel').classList.contains('hidden');
}
