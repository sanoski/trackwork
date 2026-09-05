/* The only fetch layer for the JSON API. A 401 clears the user and raises an event that
   auth.js turns into the sign-in screen. Nothing else in the app calls fetch for /api paths. */
import { state } from './state.js';

export async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  };
  if (body !== null) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (res.status === 401) {
    state.user = null;
    document.dispatchEvent(new CustomEvent('auth:unauthorized'));
    return null;
  }
  return res;
}

/* Read a JSON error body's `detail`, or a fallback message. */
export async function errorDetail(res, fallback) {
  const data = await res.json().catch(() => ({}));
  const detail = data && data.detail;
  if (Array.isArray(detail)) return detail.map(d => d.msg || String(d)).join('; ') || fallback;
  return detail || fallback;
}
