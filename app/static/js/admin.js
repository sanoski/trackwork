/* Users & Settings: accounts and roles, organisation settings (who gets the report, outgoing
   mail, names), and the weekly report timer. Admin only. Loaded on demand. */
import { api, errorDetail } from './api.js';
import { escHtml, showMsg } from './util.js';
import { openScreen } from './panel.js';

const ROLES = ['admin', 'entry', 'viewer'];
const DAYS = [['sun', 'Sunday'], ['mon', 'Monday'], ['tue', 'Tuesday'], ['wed', 'Wednesday'],
              ['thu', 'Thursday'], ['fri', 'Friday'], ['sat', 'Saturday']];

export async function openAdminScreen(tab = 'users') {
  const body = openScreen('Users & Settings', `
    <div class="panel-tabs">
      <button type="button" class="panel-tab${tab === 'users' ? ' active' : ''}" data-tab="users">Users</button>
      <button type="button" class="panel-tab${tab === 'settings' ? ' active' : ''}" data-tab="settings">Email &amp; Names</button>
      <button type="button" class="panel-tab${tab === 'schedule' ? ' active' : ''}" data-tab="schedule">Weekly Report</button>
      <button type="button" class="panel-tab${tab === 'ai' ? ' active' : ''}" data-tab="ai">AI (Claude)</button>
    </div>
    <div id="admin-tab-body"><p class="text-muted text-sm">Loading...</p></div>`);
  body.querySelectorAll('.panel-tab').forEach(b => b.addEventListener('click', () => openAdminScreen(b.dataset.tab)));
  const host = body.querySelector('#admin-tab-body');
  if (tab === 'users') await renderUsers(host);
  else if (tab === 'settings') await renderSettings(host);
  else if (tab === 'ai') await renderAi(host);
  else await renderSchedule(host);
}

// ── Users ──────────────────────────────────────────────────────────────────────

async function renderUsers(host) {
  const res = await api('GET', '/api/admin/users');
  if (!res) return;
  const users = res.ok ? await res.json() : [];
  host.innerHTML = `
    <p class="panel-intro"><b>Admin</b> manages everything. <b>Entry</b> logs and corrects work (the tie gang). <b>Viewer</b> can look and generate reports, nothing more.</p>
    <table class="admin-table">
      <thead><tr><th>Name</th><th>Email</th><th>Role</th><th></th></tr></thead>
      <tbody>${users.map(u => `
        <tr>
          <td>${escHtml(u.name)}</td>
          <td>${escHtml(u.email)}</td>
          <td><select class="u-role" data-email="${escHtml(u.email)}">${ROLES.map(r => `<option value="${r}"${u.role === r ? ' selected' : ''}>${r}</option>`).join('')}</select></td>
          <td class="row-actions">
            <button type="button" class="row-act" data-pw="${escHtml(u.email)}">Password</button>
            <button type="button" class="row-act danger" data-del="${escHtml(u.email)}">Delete</button>
          </td>
        </tr>`).join('')}
      </tbody>
    </table>
    <p id="users-msg" class="msg hidden"></p>
    <div id="pw-box" class="hidden">
      <h4>New password for <span id="pw-email"></span></h4>
      <form id="pw-form" novalidate>
        <div class="form-row">
          <div class="form-group"><input type="password" id="pw-new" minlength="8" maxlength="128" placeholder="8 or more characters" autocomplete="new-password"></div>
          <div class="form-group"><button type="submit" class="btn-primary">Save Password</button></div>
        </div>
      </form>
    </div>
    <h4>Add a user</h4>
    <form id="user-form" novalidate>
      <div class="form-row">
        <div class="form-group"><label for="au-name">Name</label><input type="text" id="au-name" maxlength="100" required></div>
        <div class="form-group"><label for="au-email">Email</label><input type="email" id="au-email" maxlength="254" required></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label for="au-role">Role</label><select id="au-role">${ROLES.map(r => `<option value="${r}"${r === 'entry' ? ' selected' : ''}>${r}</option>`).join('')}</select></div>
        <div class="form-group"><label for="au-password">Password <span class="text-muted">(8 or more characters)</span></label><input type="password" id="au-password" minlength="8" maxlength="128" autocomplete="new-password" required></div>
      </div>
      <button type="submit" class="btn-primary">+ Add User</button>
    </form>`;
  const msgEl = host.querySelector('#users-msg');
  const userUrl = email => `/api/admin/users/${encodeURIComponent(email)}`;

  host.querySelectorAll('.u-role').forEach(sel => sel.addEventListener('change', async () => {
    const res = await api('PATCH', userUrl(sel.dataset.email), { role: sel.value });
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not change the role.'), 'error'); await renderUsers(host); return; }
    showMsg(msgEl, `${sel.dataset.email} is now ${sel.value}.`, 'success');
  }));
  const pwBox = host.querySelector('#pw-box');
  host.querySelectorAll('[data-pw]').forEach(b => b.addEventListener('click', () => {
    pwBox.classList.remove('hidden');
    pwBox.dataset.email = b.dataset.pw;
    pwBox.querySelector('#pw-email').textContent = b.dataset.pw;
    pwBox.querySelector('#pw-new').value = '';
    pwBox.querySelector('#pw-new').focus();
  }));
  host.querySelector('#pw-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const pw = pwBox.querySelector('#pw-new').value;
    if (pw.length < 8) { showMsg(msgEl, 'Passwords need 8 or more characters.', 'error'); return; }
    const res = await api('PATCH', userUrl(pwBox.dataset.email), { password: pw });
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not set the password.'), 'error'); return; }
    pwBox.classList.add('hidden');
    showMsg(msgEl, `Password updated for ${pwBox.dataset.email}.`, 'success');
  });
  host.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm(`Delete the account ${b.dataset.del}?`)) return;
    const res = await api('DELETE', userUrl(b.dataset.del));
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not delete.'), 'error'); return; }
    await renderUsers(host);
  }));
  host.querySelector('#user-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      name: host.querySelector('#au-name').value.trim(),
      email: host.querySelector('#au-email').value.trim(),
      role: host.querySelector('#au-role').value,
      password: host.querySelector('#au-password').value,
    };
    if (!payload.name || !payload.email || payload.password.length < 8) {
      showMsg(msgEl, 'Name, email, and a password of 8 or more characters are required.', 'error');
      return;
    }
    const res = await api('POST', '/api/admin/users', payload);
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not add the user.'), 'error'); return; }
    await renderUsers(host);
  });
}

// ── Email & names ───────────────────────────────────────────────────────────────

async function renderSettings(host) {
  const res = await api('GET', '/api/admin/settings');
  if (!res) return;
  const s = await res.json();
  const v = id => host.querySelector('#' + id).value.trim();
  host.innerHTML = `
    <form id="settings-form" novalidate>
      <h4>Names</h4>
      <div class="form-row">
        <div class="form-group"><label for="as-org">Organisation</label><input type="text" id="as-org" value="${escHtml(s.org_name)}" maxlength="100"></div>
        <div class="form-group"><label for="as-app">App name</label><input type="text" id="as-app" value="${escHtml(s.app_name)}" maxlength="100"></div>
      </div>
      <h4>Who gets the weekly report</h4>
      <div class="form-group"><label for="as-recipients">Recipients <span class="text-muted">(comma separated)</span></label>
        <input type="text" id="as-recipients" value="${escHtml((s.report_recipients || []).join(', '))}" placeholder="boss@railroad.com, office@railroad.com"></div>
      <div class="form-group"><label for="as-sender">From address</label>
        <input type="email" id="as-sender" value="${escHtml(s.report_sender || '')}" placeholder="reports@railroad.com"></div>
      <h4>Outgoing mail (SMTP)</h4>
      <div class="form-row">
        <div class="form-group"><label for="as-host">Server</label><input type="text" id="as-host" value="${escHtml(s.smtp.host || '')}" placeholder="smtp.office365.com"></div>
        <div class="form-group"><label for="as-port">Port</label><input type="number" id="as-port" value="${s.smtp.port || 587}" min="1" max="65535"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label for="as-user">Username</label><input type="text" id="as-user" value="${escHtml(s.smtp.user || '')}" autocomplete="off"></div>
        <div class="form-group"><label for="as-password">Password ${s.smtp.password_set ? '<span class="text-muted">(set; leave blank to keep it)</span>' : ''}</label>
          <input type="password" id="as-password" autocomplete="new-password" placeholder="${s.smtp.password_set ? 'unchanged' : ''}"></div>
      </div>
      <p id="settings-msg" class="msg hidden"></p>
      <div class="panel-actions"><button type="submit" class="btn-primary btn-big">Save Settings</button></div>
    </form>
    <hr class="section-divider">
    <h4>Send a test email</h4>
    <form id="test-form" novalidate>
      <div class="form-row">
        <div class="form-group"><input type="email" id="as-test-to" placeholder="you@railroad.com"></div>
        <div class="form-group"><button type="submit" class="btn-ghost">Send Test</button></div>
      </div>
      <p id="test-msg" class="msg hidden"></p>
    </form>`;
  host.querySelector('#settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msgEl = host.querySelector('#settings-msg');
    const payload = {
      report_recipients: v('as-recipients').split(',').map(x => x.trim()).filter(Boolean),
      report_sender: v('as-sender'),
      smtp: { host: v('as-host'), port: parseInt(v('as-port'), 10) || 587, user: v('as-user'), password: v('as-password') },
    };
    if (v('as-org')) payload.org_name = v('as-org');
    if (v('as-app')) payload.app_name = v('as-app');
    const res = await api('PUT', '/api/admin/settings', payload);
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not save.'), 'error'); return; }
    host.querySelector('#as-password').value = '';
    showMsg(msgEl, 'Settings saved.', 'success');
  });
  host.querySelector('#test-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msgEl = host.querySelector('#test-msg');
    const to = v('as-test-to');
    if (!to) { showMsg(msgEl, 'Enter an address to send the test to.', 'error'); return; }
    showMsg(msgEl, 'Sending...', 'success');
    const res = await api('POST', '/api/admin/settings/test-email', { to });
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'The test email could not be sent.'), 'error'); return; }
    const data = await res.json();
    showMsg(msgEl, `Test email sent to ${data.sent_to.join(', ')}.`, 'success');
  });
}

// ── Weekly report timer ─────────────────────────────────────────────────────────

async function renderSchedule(host) {
  const res = await api('GET', '/api/admin/scheduler');
  if (!res) return;
  const st = await res.json();
  const sch = st.schedule;
  const hhmm = `${String(sch.hour).padStart(2, '0')}:${String(sch.minute).padStart(2, '0')}`;
  host.innerHTML = `
    <p class="panel-intro">The weekly report is built and emailed from inside the app. There is no cron job or task scheduler to set up: pick the day and time and save.</p>
    <div class="kv"><b>Timer</b> ${st.running ? 'running' : 'not running'} · ${st.enabled ? 'on' : 'off'}</div>
    <div class="kv"><b>Next run</b> ${st.next_run ? escHtml(st.next_run) : '-'}</div>
    <div class="kv"><b>Last run</b> ${st.last_run ? escHtml(st.last_run) : 'never'}${st.last_error ? ` <span class="val-negative">(error: ${escHtml(st.last_error)})</span>` : ''}</div>
    <div class="kv"><b>Last sent</b> ${st.last_sent_week ? `week of ${escHtml(st.last_sent_week)} to ${escHtml((st.last_recipients || []).join(', '))}` : 'nothing sent yet'}</div>
    <form id="sched-form" novalidate style="margin-top:1rem">
      <label class="check-row"><input type="checkbox" id="sc-enabled"${sch.enabled ? ' checked' : ''}> Send the weekly report automatically</label>
      <div class="form-row">
        <div class="form-group"><label for="sc-day">Day</label><select id="sc-day">${DAYS.map(([val, label]) => `<option value="${val}"${sch.day_of_week === val ? ' selected' : ''}>${label}</option>`).join('')}</select></div>
        <div class="form-group"><label for="sc-time">Time</label><input type="time" id="sc-time" value="${hhmm}"></div>
      </div>
      <div class="form-group"><label for="sc-tz">Time zone</label><input type="text" id="sc-tz" value="${escHtml(sch.timezone)}" placeholder="America/New_York"></div>
      <p id="sched-msg" class="msg hidden"></p>
      <div class="panel-actions">
        <button type="submit" class="btn-primary btn-big">Save Schedule</button>
        <button type="button" id="sc-run" class="btn-ghost">Send This Week's Report Now</button>
      </div>
    </form>`;
  host.querySelector('#sched-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msgEl = host.querySelector('#sched-msg');
    const [h, m] = (host.querySelector('#sc-time').value || '08:00').split(':').map(x => parseInt(x, 10));
    const payload = { schedule: {
      enabled: host.querySelector('#sc-enabled').checked,
      day_of_week: host.querySelector('#sc-day').value,
      hour: h, minute: m,
      timezone: host.querySelector('#sc-tz').value.trim() || 'America/New_York',
    } };
    const res = await api('PUT', '/api/admin/settings', payload);
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not save.'), 'error'); return; }
    await renderSchedule(host);
    showMsg(host.querySelector('#sched-msg'), 'Schedule saved.', 'success');
  });
  host.querySelector('#sc-run').addEventListener('click', async () => {
    const msgEl = host.querySelector('#sched-msg');
    if (!confirm("Send this week's report to the configured recipients right now?")) return;
    showMsg(msgEl, 'Building and sending...', 'success');
    const res = await api('POST', '/api/admin/scheduler/run-now');
    if (!res) return;
    const r = await res.json().catch(() => ({}));
    if (!res.ok) { showMsg(msgEl, r.detail || 'Could not run.', 'error'); return; }
    if (r.ran) showMsg(msgEl, `Sent to ${(r.recipients || []).join(', ')}.`, 'success');
    else showMsg(msgEl, `Not sent: ${r.reason}.`, 'error');
  });
}


// ── AI assistant (MCP) access ──────────────────────────────────────────────────

const PROVIDER_HELP = {
  token: 'Per-user tokens. Create one for a person below and paste it into Claude Code or the Claude desktop app as a bearer token. Revoke it here at any time.',
  azure: 'People sign in with their Microsoft 365 account. Add the URL as a custom connector in claude.ai and sign in when prompted.',
  google: 'People sign in with their Google account. Add the URL as a custom connector in claude.ai and sign in when prompted.',
  github: 'People sign in with GitHub. Add the URL as a custom connector in claude.ai and sign in when prompted.',
  none: 'No authentication. Only acceptable on a private development machine.',
};

async function renderAi(host) {
  const [infoRes, usersRes] = await Promise.all([api('GET', '/api/admin/mcp-tokens'), api('GET', '/api/admin/users')]);
  if (!infoRes || !usersRes) return;
  const info = await infoRes.json();
  const users = usersRes.ok ? await usersRes.json() : [];
  const tokens = info.tokens || [];
  const url = info.url || '(set MCP_BASE_URL in .env)';
  const claudeCode = info.url
    ? `claude mcp add --transport http mow-tracker ${info.url} --header "Authorization: Bearer YOUR-TOKEN"`
    : 'claude mcp add --transport http mow-tracker https://YOUR-HOST/mcp --header "Authorization: Bearer YOUR-TOKEN"';
  host.innerHTML = `
    <p class="panel-intro">Claude (or another AI assistant) can log and read work through the app's MCP server, using the same rules as this screen. It is ${info.enabled ? '<b>on</b>' : '<b>off</b> (set <code>MCP_ENABLED=true</code> in .env to turn it on)'}.</p>
    <div class="kv"><b>Address</b> <code>${escHtml(url)}</code></div>
    <div class="kv"><b>Sign-in method</b> ${escHtml(info.provider)}</div>
    <p class="text-muted text-sm">${escHtml(PROVIDER_HELP[info.provider] || '')}</p>
    ${info.provider === 'token' ? `
    <h4>Tokens</h4>
    ${tokens.length ? `<table class="admin-table"><thead><tr><th>Who</th><th>Label</th><th>Expires</th><th></th></tr></thead><tbody>${
      tokens.map(t => `<tr${t.revoked ? ' class="text-muted"' : ''}>
        <td>${escHtml(t.email)}</td><td>${escHtml(t.label)}</td><td>${escHtml(t.expires.slice(0, 10))}${t.revoked ? ' (revoked)' : ''}</td>
        <td class="row-actions">${t.revoked ? '' : `<button type="button" class="row-act danger" data-revoke="${escHtml(t.id)}">Revoke</button>`}</td>
      </tr>`).join('')}</tbody></table>` : '<p class="text-muted text-sm">No tokens yet.</p>'}
    <p id="ai-msg" class="msg hidden"></p>
    <div id="ai-new-token" class="hidden">
      <h4>New token (copy it now; it will not be shown again)</h4>
      <textarea id="ai-token-text" readonly rows="4"></textarea>
      <p class="text-muted text-sm">Claude Code, in a terminal:</p>
      <textarea readonly rows="2">${escHtml(claudeCode)}</textarea>
    </div>
    <h4>Create a token</h4>
    <form id="ai-form" novalidate>
      <div class="form-row">
        <div class="form-group"><label for="ai-email">For</label><select id="ai-email">${users.map(u => `<option value="${escHtml(u.email)}">${escHtml(u.name)} (${escHtml(u.role)})</option>`).join('')}</select></div>
        <div class="form-group"><label for="ai-label">Label</label><input type="text" id="ai-label" maxlength="80" placeholder="e.g. Claude on Mike's phone"></div>
      </div>
      <div class="form-group"><label for="ai-days">Valid for (days)</label><input type="number" id="ai-days" value="90" min="1" max="365"></div>
      <button type="submit" class="btn-primary">Create Token</button>
    </form>` : ''}`;
  if (info.provider !== 'token') return;
  const msgEl = host.querySelector('#ai-msg');
  host.querySelectorAll('[data-revoke]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Revoke this token? The assistant using it will stop working immediately.')) return;
    const res = await api('DELETE', `/api/admin/mcp-tokens/${encodeURIComponent(b.dataset.revoke)}`);
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not revoke.'), 'error'); return; }
    await renderAi(host);
  }));
  host.querySelector('#ai-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      email: host.querySelector('#ai-email').value,
      label: host.querySelector('#ai-label').value.trim(),
      days: parseInt(host.querySelector('#ai-days').value, 10) || 90,
    };
    if (!payload.label) { showMsg(msgEl, 'Give the token a label.', 'error'); return; }
    const res = await api('POST', '/api/admin/mcp-tokens', payload);
    if (!res) return;
    if (!res.ok) { showMsg(msgEl, await errorDetail(res, 'Could not create the token.'), 'error'); return; }
    const data = await res.json();
    const box = host.querySelector('#ai-new-token');
    box.classList.remove('hidden');
    box.querySelector('#ai-token-text').value = data.token;
    box.querySelector('#ai-token-text').focus();
    box.querySelector('#ai-token-text').select();
    showMsg(msgEl, `Token created for ${payload.email}. Copy it from the box below.`, 'success');
  });
}
