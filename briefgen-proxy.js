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

// For any alkira.net email also include alkira.com and vice versa
function expandAlkiraEmails(emails) {
  const result = new Set(emails);
  for (const email of emails) {
    if (email.endsWith('@alkira.net')) result.add(email.replace('@alkira.net', '@alkira.com'));
    if (email.endsWith('@alkira.com')) result.add(email.replace('@alkira.com', '@alkira.net'));
  }
  return [...result];
}

// EFS-backed OTP codes so both instances can verify regardless of which sent the email
function readOtps() {
  try { return JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'otps.json'), 'utf8')); }
  catch(e) { return {}; }
}
function writeOtps(data) {
  fs.writeFileSync(path.join(DATA_DIR, 'otps.json'), JSON.stringify(data, null, 2));
}
setInterval(() => {
  try {
    const all = readOtps(); const now = Date.now(); let changed = false;
    for (const [k, v] of Object.entries(all)) { if (now - v.createdAt > 10 * 60 * 1000) { delete all[k]; changed = true; } }
    if (changed) writeOtps(all);
  } catch(e) {}
}, 5 * 60 * 1000);

const SSO_SECRET = process.env.SSO_SECRET || 'af3438681440671902980c68fba95e9a8ccab4f7e22be92bf1edf68be6502eae';
function verifySsoToken(token) {
  if (!SSO_SECRET || !token) return null;
  const dot = token.lastIndexOf('.');
  if (dot === -1) return null;
  const b64 = token.slice(0, dot);
  const sig  = token.slice(dot + 1);
  const expected = crypto.createHmac('sha256', SSO_SECRET).update(b64).digest('hex');
  try {
    const eBuf = Buffer.from(expected, 'hex');
    const sBuf = Buffer.from(sig,      'hex');
    if (eBuf.length !== sBuf.length || !crypto.timingSafeEqual(eBuf, sBuf)) return null;
  } catch { return null; }
  const payload = JSON.parse(Buffer.from(b64, 'base64url').toString());
  if (Date.now() > payload.exp) return null;
  return payload;
}

function readSessions() {
  try { return JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'sessions.json'), 'utf8')); }
  catch(e) { return {}; }
}
function writeSessions(data) {
  fs.writeFileSync(path.join(DATA_DIR, 'sessions.json'), JSON.stringify(data, null, 2));
}

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
  const all = readSessions();
  const s = all[sid];
  if (!s || s.expires < Date.now()) { delete all[sid]; writeSessions(all); return null; }
  return s;
}

function setCookie(res, sid) {
  const exp = new Date(Date.now() + 7 * 86400 * 1000).toUTCString();
  res.setHeader('Set-Cookie', `briefgen_session=${sid}; Path=/; HttpOnly; Secure; SameSite=Strict; Expires=${exp}`);
}

function clearCookie(res) {
  res.setHeader('Set-Cookie', 'briefgen_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0');
}

async function sendCodeEmail(to, code) {
  await ses.send(new SendEmailCommand({
    Source: FROM,
    Destination: { ToAddresses: [to] },
    Message: {
      Subject: { Data: 'Your sign-in code — Alkira Brief Generator' },
      Body: {
        Html: {
          Data: `<!DOCTYPE html><html><body style="font-family:sans-serif;background:#f4f7fb;padding:40px 20px">
<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:40px;box-shadow:0 4px 24px rgba(0,0,0,.08)">
  <div style="text-align:center;margin-bottom:28px">
    <img src="https://briefgen.partners.alkira.cc/Alkira-Logo-Registered-Color.png" style="height:44px;width:auto" alt="Alkira">
  </div>
  <h2 style="color:#0D2F5E;margin:0 0 12px;font-size:20px;text-align:center">Your Sign-In Code</h2>
  <p style="color:#6b7280;font-size:14px;line-height:1.6;text-align:center;margin:0 0 24px">Enter this code to sign in to the Brief Generator. It expires in 10 minutes.</p>
  <div style="font-size:40px;font-weight:700;letter-spacing:10px;text-align:center;color:#0D2F5E;padding:20px 0;border-radius:8px;background:#f0f4ff;margin:0 0 24px">${code}</div>
  <p style="color:#9ca3af;font-size:12px;text-align:center;margin:0">If you didn't request this, you can safely ignore this email.</p>
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

    // ── GET /api/auth/sso — dashboard admin auto-login ─────────────────
    if (req.method === 'GET' && p === '/api/auth/sso') {
      const ssoPayload = verifySsoToken(url.searchParams.get('token'));
      if (ssoPayload) {
        const sid = mkRandom();
        const all = readSessions();
        all[sid] = { email: ssoPayload.email, role: 'admin', expires: Date.now() + 7 * 86400 * 1000 };
        writeSessions(all);
        const exp = new Date(Date.now() + 7 * 86400 * 1000).toUTCString();
        res.setHeader('Set-Cookie', [
          `briefgen_session=${sid}; Path=/; HttpOnly; Secure; SameSite=Strict; Expires=${exp}`,
          'briefgen_no_sso=; Path=/; Secure; SameSite=Lax; Max-Age=0',
        ]);
      }
      res.writeHead(302, { Location: '/' });
      return res.end();
    }

    // ── POST /api/auth/send — send 6-digit code ────────────────────────
    if (req.method === 'POST' && p === '/api/auth/send') {
      const { email } = await readBody(req);
      if (!email || !email.includes('@')) return json(res, 400, { error: 'Invalid email' });
      const norm   = email.toLowerCase().trim();
      const domain = norm.split('@')[1];
      const admins  = expandAlkiraEmails(readJson('admins.json', []));
      const firstRun = admins.length === 0;
      const domains = readJson('domains.json', []);
      if (!firstRun && !admins.includes(norm) && !domains.includes(domain)) {
        return json(res, 403, { error: 'Domain not authorized' });
      }
      if (!firstRun && admins.includes(norm)) return json(res, 200, { ok: false, adminSso: true });
      const code = String(Math.floor(100000 + Math.random() * 900000));
      const all = readOtps();
      all[norm] = { code, createdAt: Date.now(), attempts: 0 };
      writeOtps(all);
      try {
        await sendCodeEmail(norm, code);
        console.log(`[auth/send] code sent to ${norm}`);
      } catch(e) {
        console.error(`[auth/send] SES error for ${norm}:`, e.message);
        return json(res, 500, { error: 'Failed to send email' });
      }
      return json(res, 200, { ok: true });
    }

    // ── POST /api/auth/verify — validate 6-digit code ──────────────────
    if (req.method === 'POST' && p === '/api/auth/verify') {
      const { email, code } = await readBody(req);
      if (!email || !code) return json(res, 400, { error: 'Email and code required' });
      const norm = email.toLowerCase().trim();
      const all = readOtps();
      const entry = all[norm];
      if (!entry) return json(res, 401, { error: 'No code found. Please request a new one.' });
      if (Date.now() - entry.createdAt > 10 * 60 * 1000) {
        delete all[norm]; writeOtps(all);
        return json(res, 401, { error: 'Code expired. Please request a new one.' });
      }
      if (entry.attempts >= 5) return json(res, 429, { error: 'Too many attempts. Please request a new code.' });
      if (entry.code !== String(code).trim()) {
        entry.attempts += 1; writeOtps(all);
        const left = 5 - entry.attempts;
        return json(res, 401, { error: `Incorrect code. ${left} attempt${left !== 1 ? 's' : ''} remaining.` });
      }
      delete all[norm]; writeOtps(all);
      const admins = expandAlkiraEmails(readJson('admins.json', []));
      const role = admins.includes(norm) ? 'admin' : 'user';
      const sid = mkRandom();
      const sessions = readSessions();
      sessions[sid] = { email: norm, role, expires: Date.now() + 7 * 86400 * 1000 };
      writeSessions(sessions);
      setCookie(res, sid);
      return json(res, 200, { ok: true, redirect: '/' });
    }

    // ── GET /api/auth/signout — clears session and redirects to auth page ─
    if (req.method === 'GET' && p === '/api/auth/signout') {
      const sid = parseCookies(req)['briefgen_session'];
      if (sid) { const all = readSessions(); delete all[sid]; writeSessions(all); }
      res.setHeader('Set-Cookie', [
        'briefgen_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0',
        'briefgen_no_sso=1; Path=/; Secure; SameSite=Lax',
      ]);
      res.writeHead(302, { Location: '/auth.html?signed_out=1' });
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
      if (sid) { const all = readSessions(); delete all[sid]; writeSessions(all); }
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

    // ── GET /api/domains ────────────────────────────────────────────────
    if (req.method === 'GET' && p === '/api/domains') {
      const s = getSession(req);
      if (!s || s.role !== 'admin') return json(res, 401, { error: 'Unauthorized' });
      return json(res, 200, { domains: readJson('domains.json', []) });
    }

    json(res, 404, { error: 'Not found' });
  } catch(e) {
    console.error(`[${new Date().toISOString()}]`, e.message);
    json(res, 500, { error: 'Internal error' });
  }
}).listen(PORT, '127.0.0.1', () => {
  console.log(`Brief Generator auth proxy on port ${PORT}`);
});
