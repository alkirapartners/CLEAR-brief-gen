// Brief Generator auth backend — port 3461
const http   = require('http');
const crypto = require('crypto');
const fs     = require('fs');
const path   = require('path');
const { SESClient, SendEmailCommand } = require('@aws-sdk/client-ses');

const PORT     = 3461;
const DATA_DIR = '/var/www/briefgen/data';
const SITE     = 'https://briefgen.partners.alkira.cc';
const FROM     = 'no-reply@alkira.cc';

const ses = new SESClient({ region: 'us-west-2' });

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

function readJson(file, def) {
  try { return JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), 'utf8')); }
  catch(e) { return def; }
}
function writeJson(file, data) {
  fs.writeFileSync(path.join(DATA_DIR, file), JSON.stringify(data, null, 2));
}

// In-memory sessions (7-day TTL) and pending magic-link tokens (15-min TTL)
const sessions = new Map();
const tokens   = new Map();

function mkRandom() { return crypto.randomBytes(32).toString('hex'); }

function parseCookies(req) {
  return Object.fromEntries(
    (req.headers.cookie || '').split(';')
      .map(c => c.trim().split('='))
      .filter(a => a.length >= 2)
      .map(([k, ...v]) => [k.trim(), v.join('=').trim()])
  );
}

function getSession(req) {
  const sid = parseCookies(req)['briefgen_session'];
  if (!sid) return null;
  const s = sessions.get(sid);
  if (!s || s.expires < Date.now()) { sessions.delete(sid); return null; }
  return s;
}

function setCookie(res, sid) {
  const exp = new Date(Date.now() + 7 * 86400 * 1000).toUTCString();
  res.setHeader('Set-Cookie', `briefgen_session=${sid}; Path=/; HttpOnly; Secure; SameSite=Strict; Expires=${exp}`);
}

function clearCookie(res) {
  res.setHeader('Set-Cookie', 'briefgen_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0');
}

async function sendMagicLink(to, link, isAdmin) {
  const subject = isAdmin
    ? 'Your admin sign-in link — Alkira Brief Generator'
    : 'Your access link — Alkira Brief Generator';
  const heading = isAdmin ? 'Admin Sign In' : 'Access the Brief Generator';
  const btnText = isAdmin ? 'Open Admin Panel →' : 'Open Brief Generator →';

  await ses.send(new SendEmailCommand({
    Source: FROM,
    Destination: { ToAddresses: [to] },
    Message: {
      Subject: { Data: subject },
      Body: {
        Html: {
          Data: `<!DOCTYPE html><html><body style="font-family:sans-serif;background:#f4f7fb;padding:40px 20px">
<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:40px;box-shadow:0 4px 24px rgba(0,0,0,.08)">
  <div style="text-align:center;margin-bottom:28px">
    <img src="https://briefgen.partners.alkira.cc/Alkira-Logo-Registered-Color.png" style="height:44px;width:auto" alt="Alkira">
  </div>
  <h2 style="color:#0D2F5E;margin:0 0 12px;font-size:20px;text-align:center">${heading}</h2>
  <p style="color:#6b7280;font-size:14px;line-height:1.6;text-align:center;margin:0 0 28px">Click the button below to sign in. This link expires in 15 minutes.</p>
  <div style="text-align:center">
    <a href="${link}" style="display:inline-block;background:#0D2F5E;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:15px">${btnText}</a>
  </div>
  <p style="color:#9ca3af;font-size:12px;text-align:center;margin:24px 0 0">If you didn't request this, you can safely ignore this email.</p>
</div></body></html>`
        }
      }
    }
  }));
}

function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let s = '';
    req.on('data', c => s += c);
    req.on('end', () => { try { resolve(JSON.parse(s || '{}')); } catch(e) { resolve({}); } });
    req.on('error', reject);
  });
}

http.createServer(async (req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  const url = new URL(req.url, 'http://localhost');
  const p   = url.pathname;

  try {
    // ── GET /api/auth/check ─ internal nginx auth_request endpoint ──────
    // Returns 200 + X-Auth-Email header if session valid, 401 otherwise
    if (req.method === 'GET' && p === '/api/auth/check') {
      const s = getSession(req);
      if (!s) return json(res, 401, { error: 'Unauthorized' });
      res.setHeader('X-Auth-Email', s.email);
      return json(res, 200, { ok: true });
    }

    // ── POST /api/auth/request ──────────────────────────────────────────
    if (req.method === 'POST' && p === '/api/auth/request') {
      const { email, context } = await readBody(req);
      if (!email || !email.includes('@')) return json(res, 400, { error: 'Invalid email' });

      const norm   = email.toLowerCase().trim();
      const domain = norm.split('@')[1];
      const admins = readJson('admins.json', []);
      const firstRun = admins.length === 0;

      console.log(`[auth/request] context=${context} email=${norm} isAdmin=${admins.includes(norm)} firstRun=${firstRun}`);

      let role;
      if (context === 'admin') {
        if (!firstRun && !admins.includes(norm)) {
          console.log(`[auth/request] silent fail — not in admins list`);
          return json(res, 200, { ok: true });
        }
        role = 'admin';
      } else {
        const domains = readJson('domains.json', []);
        if (!domains.includes(domain)) {
          console.log(`[auth/request] domain not authorized: ${domain}`);
          return json(res, 403, { error: 'Domain not authorized' });
        }
        role = admins.includes(norm) ? 'admin' : 'user';
      }

      const token = mkRandom();
      tokens.set(token, { email: norm, role, expires: Date.now() + 15 * 60 * 1000 });
      setTimeout(() => tokens.delete(token), 15 * 60 * 1000);

      const to   = context === 'admin' ? '/admin.html' : `/?auth_email=${encodeURIComponent(norm)}`;
      const link = `${SITE}/api/auth/verify?token=${token}&to=${encodeURIComponent(to)}`;
      try {
        await sendMagicLink(norm, link, context === 'admin');
        console.log(`[auth/request] email sent to ${norm}`);
      } catch(e) {
        console.error(`[auth/request] SES error for ${norm}:`, e.message);
        return json(res, 500, { error: 'Failed to send email' });
      }
      return json(res, 200, { ok: true });
    }

    // ── GET /api/auth/verify ────────────────────────────────────────────
    if (req.method === 'GET' && p === '/api/auth/verify') {
      const token = url.searchParams.get('token');
      const to    = url.searchParams.get('to') || '/';
      const t     = token && tokens.get(token);
      if (!t || t.expires < Date.now()) {
        tokens.delete(token);
        res.writeHead(302, { Location: `/auth.html?error=expired` });
        return res.end();
      }
      tokens.delete(token);
      const sid = mkRandom();
      sessions.set(sid, { email: t.email, role: t.role, expires: Date.now() + 7 * 86400 * 1000 });
      setCookie(res, sid);
      res.writeHead(302, { Location: to });
      return res.end();
    }

    // ── GET /api/auth/signout — clears session and redirects to auth page ─
    if (req.method === 'GET' && p === '/api/auth/signout') {
      const sid = parseCookies(req)['briefgen_session'];
      if (sid) sessions.delete(sid);
      clearCookie(res);
      res.writeHead(302, { Location: '/auth.html' });
      return res.end();
    }

    // ── GET /api/auth/session ───────────────────────────────────────────
    if (req.method === 'GET' && p === '/api/auth/session') {
      const s = getSession(req);
      if (!s) return json(res, 200, { ok: false });
      return json(res, 200, { ok: true, email: s.email, role: s.role });
    }

    // ── POST /api/auth/logout ───────────────────────────────────────────
    if (req.method === 'POST' && p === '/api/auth/logout') {
      const sid = parseCookies(req)['briefgen_session'];
      if (sid) sessions.delete(sid);
      clearCookie(res);
      return json(res, 200, { ok: true });
    }

    // ── GET /api/admins ─────────────────────────────────────────────────
    if (req.method === 'GET' && p === '/api/admins') {
      const admins = readJson('admins.json', []);
      if (admins.length === 0) return json(res, 200, { firstRun: true, admins: [] });
      const s = getSession(req);
      if (!s || s.role !== 'admin') return json(res, 401, { error: 'Unauthorized' });
      return json(res, 200, { admins });
    }

    // ── POST /api/admins ────────────────────────────────────────────────
    if (req.method === 'POST' && p === '/api/admins') {
      const admins   = readJson('admins.json', []);
      const firstRun = admins.length === 0;
      if (!firstRun) {
        const s = getSession(req);
        if (!s || s.role !== 'admin') return json(res, 401, { error: 'Unauthorized' });
      }
      const { add, remove } = await readBody(req);
      let list = [...admins];
      if (add)    { const e = add.toLowerCase().trim(); if (!list.includes(e)) list.push(e); }
      if (remove) { list = list.filter(x => x !== remove.toLowerCase().trim()); }
      writeJson('admins.json', list);
      return json(res, 200, { admins: list });
    }

    // ── GET /api/domains ────────────────────────────────────────────────
    if (req.method === 'GET' && p === '/api/domains') {
      const s = getSession(req);
      if (!s || s.role !== 'admin') return json(res, 401, { error: 'Unauthorized' });
      return json(res, 200, { domains: readJson('domains.json', []) });
    }

    // ── POST /api/domains ───────────────────────────────────────────────
    if (req.method === 'POST' && p === '/api/domains') {
      const s = getSession(req);
      if (!s || s.role !== 'admin') return json(res, 401, { error: 'Unauthorized' });
      const { add, remove } = await readBody(req);
      let list = readJson('domains.json', []);
      if (add)    { const d = add.toLowerCase().trim().replace(/^@/, ''); if (!list.includes(d)) list.push(d); }
      if (remove) { list = list.filter(x => x !== remove.toLowerCase().trim().replace(/^@/, '')); }
      writeJson('domains.json', list);
      return json(res, 200, { domains: list });
    }

    json(res, 404, { error: 'Not found' });
  } catch(e) {
    console.error(`[${new Date().toISOString()}]`, e.message);
    json(res, 500, { error: 'Internal error' });
  }
}).listen(PORT, '127.0.0.1', () => {
  console.log(`Brief Generator auth proxy on port ${PORT}`);
  syncAdminsFromIntranet();
});

function syncAdminsFromIntranet() {
  http.get('http://127.0.0.1:3457/api/internal/team-emails', res => {
    let body = '';
    res.on('data', c => body += c);
    res.on('end', () => {
      try {
        const { emails } = JSON.parse(body);
        if (!Array.isArray(emails)) return;
        const current = readJson('admins.json', []);
        const merged  = [...current];
        let added = 0;
        for (const e of emails) {
          const norm = e.toLowerCase().trim();
          if (norm && !merged.includes(norm)) { merged.push(norm); added++; }
        }
        if (added > 0) {
          writeJson('admins.json', merged);
          console.log(`[sync] Added ${added} admin(s) from intranet team`);
        }
      } catch(e) {
        console.error('[sync] Failed to parse team-emails response:', e.message);
      }
    });
  }).on('error', e => console.error('[sync] Could not reach intranet proxy:', e.message));
}

setInterval(syncAdminsFromIntranet, 60 * 60 * 1000);
