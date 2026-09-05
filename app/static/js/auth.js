/* Sign-in, sign-out, and who-can-do-what. Emits auth:login and auth:logout; main.js reacts. */
import { state } from './state.js';
import { showMsg } from './util.js';

export function canWrite() {
  return !!state.user && (state.user.role === 'admin' || state.user.role === 'entry');
}

export function isAdmin() {
  return !!state.user && state.user.role === 'admin';
}

export async function checkAuth() {
  try {
    const res = await fetch('/auth/me', { credentials: 'include' });
    state.user = res.ok ? await res.json() : null;
  } catch {
    state.user = null;
  }
  updateAuthUI();
}

export function updateAuthUI() {
  const authInfo       = document.getElementById('auth-info');
  const logoutBtn      = document.getElementById('logout-btn');
  const headerLoginBtn = document.getElementById('header-login-btn');
  const logDataBtn     = document.getElementById('log-data-btn');
  const generateBtn    = document.getElementById('generate-report-btn');

  if (state.user) {
    authInfo.textContent = state.user.name;
    logoutBtn.classList.remove('hidden');
    headerLoginBtn.classList.add('hidden');
    generateBtn.classList.remove('hidden');
    logDataBtn.classList.toggle('hidden', !canWrite());
  } else {
    authInfo.textContent = '';
    logoutBtn.classList.add('hidden');
    headerLoginBtn.classList.remove('hidden');
    generateBtn.classList.add('hidden');
    logDataBtn.classList.add('hidden');
  }
  document.body.classList.toggle('is-admin', isAdmin());
  document.body.classList.toggle('can-write', canWrite());
}

export async function handleLogin(e) {
  e.preventDefault();
  const email    = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const errEl    = document.getElementById('login-error');
  const btn      = document.getElementById('login-submit');

  errEl.classList.add('hidden');
  btn.disabled = true;
  btn.textContent = 'Signing in...';

  try {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });

    if (res.ok) {
      const data = await res.json();
      state.user = { name: data.name, role: data.role, email };
      updateAuthUI();
      hideLoginModal();
      document.dispatchEvent(new CustomEvent('auth:login'));
    } else {
      showMsg(errEl, 'Invalid email or password.', 'error');
    }
  } catch {
    showMsg(errEl, 'Network error. Please try again.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign In';
  }
}

export async function handleLogout() {
  await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
  state.user = null;
  updateAuthUI();
  document.dispatchEvent(new CustomEvent('auth:logout'));
}

export function showLoginModal() {
  document.getElementById('login-modal').classList.remove('hidden');
  document.getElementById('login-email').focus();
}

export function hideLoginModal() {
  document.getElementById('login-modal').classList.add('hidden');
  document.getElementById('login-form').reset();
  document.getElementById('login-error').classList.add('hidden');
}

/* A 401 anywhere in the API layer shows the sign-in screen (once). */
export function initAuth() {
  document.addEventListener('auth:unauthorized', () => {
    updateAuthUI();
    if (document.getElementById('login-modal').classList.contains('hidden')) showLoginModal();
  });
}
