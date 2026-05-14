#!/usr/bin/env python3
"""
git-manager-web.py — Web UI para gestión de git/GitHub en workspaces LAIA.
Ejecutar: python3 git-manager-web.py
Abrir:    http://localhost:5055
"""

from __future__ import annotations

import json
import queue
import sys
import threading
from pathlib import Path

try:
    from flask import Flask, Response, jsonify, request, stream_with_context
except ImportError:
    print("ERROR: Flask no instalado. Instalar con: pip install flask", file=sys.stderr)
    sys.exit(1)

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "git_manager",
    Path(__file__).parent / "git-manager.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
WorkspaceGitManager = _mod.WorkspaceGitManager

app = Flask(__name__)
mgr = WorkspaceGitManager()

# ─── HTML ─────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LAIA · git-manager</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #000;
    --bg-soft:  #0a0a0a;
    --bg-card:  #111;
    --bg-hover: #1a1a1a;
    --accent:   #e8185c;
    --accent-h: #ff2d6b;
    --text1:    #f5f5f5;
    --text2:    #888;
    --text3:    #555;
    --border:   rgba(255,255,255,.07);
    --border2:  rgba(255,255,255,.15);
    --green:    #22c55e;
    --yellow:   #f59e0b;
    --red:      #ef4444;
    --blue:     #3b82f6;
  }

  body { background: var(--bg); color: var(--text1); font-family: 'SF Mono', 'Fira Code', monospace; font-size: 13px; min-height: 100vh; }

  /* Header */
  header { display: flex; align-items: center; gap: 12px; padding: 14px 24px; border-bottom: 1px solid var(--border); background: var(--bg-soft); position: sticky; top: 0; z-index: 100; }
  header .logo { font-size: 15px; font-weight: 700; color: var(--text1); letter-spacing: 1px; }
  header .logo span { color: var(--accent); }
  header .subtitle { color: var(--text2); font-size: 11px; }
  header .actions { margin-left: auto; display: flex; gap: 8px; }

  /* Buttons */
  .btn { display: inline-flex; align-items: center; gap: 5px; padding: 5px 12px; border-radius: 4px; border: 1px solid var(--border2); background: var(--bg-hover); color: var(--text1); font-family: inherit; font-size: 11px; font-weight: 600; cursor: pointer; transition: all .15s; text-transform: uppercase; letter-spacing: .5px; white-space: nowrap; }
  .btn:hover { border-color: var(--accent); color: var(--accent); }
  .btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
  .btn.primary:hover { background: var(--accent-h); }
  .btn.danger { color: var(--red); border-color: var(--red); }
  .btn.danger:hover { background: rgba(239,68,68,.1); }
  .btn:disabled { opacity: .4; cursor: not-allowed; }
  .btn.sm { padding: 3px 8px; font-size: 10px; }

  /* Layout */
  main { padding: 24px; max-width: 1400px; margin: 0 auto; }
  .section-title { font-size: 10px; font-weight: 600; color: var(--text3); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 12px; }

  /* Table */
  .ws-table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; }
  table { width: 100%; border-collapse: collapse; }
  thead th { background: var(--bg-soft); color: var(--text2); font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); white-space: nowrap; }
  tbody tr { border-bottom: 1px solid var(--border); transition: background .1s; }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: var(--bg-hover); }
  tbody td { padding: 10px 14px; vertical-align: middle; }
  tbody tr.excluded { opacity: .45; }

  /* Badges */
  .badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 7px; border-radius: 3px; font-size: 10px; font-weight: 600; letter-spacing: .3px; }
  .badge.ok      { color: var(--green); background: rgba(34,197,94,.1); border: 1px solid rgba(34,197,94,.25); }
  .badge.dirty   { color: var(--yellow); background: rgba(245,158,11,.1); border: 1px solid rgba(245,158,11,.25); }
  .badge.no-sync { color: var(--yellow); background: rgba(245,158,11,.1); border: 1px solid rgba(245,158,11,.25); }
  .badge.no-git  { color: var(--text3); background: var(--bg-hover); border: 1px solid var(--border); }
  .badge.excl    { color: var(--blue); background: rgba(59,130,246,.1); border: 1px solid rgba(59,130,246,.2); }
  .badge.error   { color: var(--red); background: rgba(239,68,68,.1); border: 1px solid rgba(239,68,68,.2); }

  /* Repo chips */
  .repo-chips { display: flex; flex-wrap: wrap; gap: 4px; }
  .chip { background: var(--bg-hover); border: 1px solid var(--border2); border-radius: 3px; padding: 1px 6px; font-size: 10px; color: var(--text2); }
  .chip.has-git { color: var(--accent); border-color: rgba(232,24,92,.3); background: rgba(232,24,92,.07); }

  /* Row actions */
  .row-actions { display: flex; gap: 4px; flex-wrap: wrap; }

  /* Panel / drawer */
  .overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.7); z-index: 200; }
  .overlay.open { display: flex; align-items: flex-start; justify-content: flex-end; }
  .drawer { background: var(--bg-card); border-left: 1px solid var(--border2); width: 480px; max-width: 95vw; height: 100vh; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 20px; }
  .drawer h2 { font-size: 14px; color: var(--text1); display: flex; align-items: center; gap: 8px; }
  .drawer h2 .ws-tag { font-size: 11px; color: var(--accent); background: rgba(232,24,92,.12); border: 1px solid rgba(232,24,92,.3); border-radius: 3px; padding: 1px 7px; }

  /* Form */
  .form-group { display: flex; flex-direction: column; gap: 6px; }
  label { font-size: 10px; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: .8px; }
  input[type=text], select { background: var(--bg-hover); border: 1px solid var(--border2); border-radius: 4px; color: var(--text1); font-family: inherit; font-size: 12px; padding: 7px 10px; width: 100%; outline: none; transition: border-color .15s; }
  input[type=text]:focus, select:focus { border-color: var(--accent); }
  select option { background: var(--bg-card); }

  /* Log output */
  .log-box { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 12px; font-size: 11px; line-height: 1.7; color: var(--text2); min-height: 80px; max-height: 320px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
  .log-box .ok   { color: var(--green); }
  .log-box .err  { color: var(--red); }
  .log-box .info { color: var(--blue); }
  .log-box .warn { color: var(--yellow); }
  .log-box.hidden { display: none; }

  /* Divider */
  hr { border: none; border-top: 1px solid var(--border); }

  /* Status bar */
  #status-bar { font-size: 10px; color: var(--text3); padding: 4px 24px 8px; }
  #status-bar span { color: var(--text2); }

  /* Spinner */
  @keyframes spin { to { transform: rotate(360deg); } }
  .spin { display: inline-block; width: 10px; height: 10px; border: 2px solid var(--border2); border-top-color: var(--accent); border-radius: 50%; animation: spin .6s linear infinite; }

  /* Responsive */
  @media (max-width: 800px) {
    .hide-sm { display: none; }
    .drawer { width: 100vw; }
  }
</style>
</head>
<body>

<header>
  <div class="logo">LAIA <span>·</span> git-manager</div>
  <div class="subtitle">workspaces git &amp; GitHub</div>
  <div class="actions">
    <button class="btn" onclick="refreshAll()">↻ Refrescar</button>
  </div>
</header>

<div id="status-bar">Cargando workspaces...</div>

<main>
  <div class="section-title">Workspaces</div>
  <div class="ws-table-wrap">
    <table id="ws-table">
      <thead>
        <tr>
          <th>Workspace</th>
          <th>Estado</th>
          <th>Repos git</th>
          <th class="hide-sm">GitHub</th>
          <th class="hide-sm">Rama</th>
          <th class="hide-sm">Último sync</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody id="ws-tbody">
        <tr><td colspan="7" style="color:var(--text3);text-align:center;padding:32px">
          <div class="spin" style="width:16px;height:16px;margin:0 auto 8px"></div>
          Cargando...
        </td></tr>
      </tbody>
    </table>
  </div>
</main>

<!-- Drawer overlay -->
<div class="overlay" id="overlay" onclick="closeDrawer(event)">
  <div class="drawer" id="drawer" onclick="event.stopPropagation()">
    <!-- content injected by JS -->
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let _data = [];

// ── API helpers ────────────────────────────────────────────────────────────
async function api(url, opts = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
  return r.json();
}

// ── Render ─────────────────────────────────────────────────────────────────
function statusBadge(ws) {
  if (ws.excluded)            return '<span class="badge excl">LAIA root</span>';
  if (!ws.ok)                 return '<span class="badge error">error</span>';
  if (ws.topology === 'none') return '<span class="badge no-git">sin git</span>';
  const repos = ws.repos || [];
  const dirty   = repos.some(r => !r.git.clean);
  const noSync  = repos.some(r => !r.git.has_remote || r.git.ahead > 0);
  if (dirty)   return '<span class="badge dirty">cambios</span>';
  if (noSync)  return '<span class="badge no-sync">sin sync</span>';
  return '<span class="badge ok">ok</span>';
}

function repoChips(ws) {
  if (ws.excluded)            return '<span style="color:var(--text3);font-size:11px">→ /LAIA</span>';
  if (ws.topology === 'none') return '<span style="color:var(--text3);font-size:11px">ninguno</span>';
  return (ws.repos || []).map(r => {
    const ahead = r.git.ahead > 0 ? ` ↑${r.git.ahead}` : '';
    const dirty = !r.git.clean ? ' ●' : '';
    return `<span class="chip has-git" title="${r.rel_path}">${r.name}${ahead}${dirty}</span>`;
  }).join('');
}

function githubCell(ws) {
  if (ws.excluded || ws.topology === 'none') return '—';
  return (ws.repos || [])
    .map(r => r.github_repo || '—')
    .filter((v, i, a) => a.indexOf(v) === i)
    .join(', ') || '—';
}

function branchCell(ws) {
  if (ws.excluded || ws.topology === 'none') return '—';
  const branches = [...new Set((ws.repos || []).map(r => r.git.branch))];
  return branches.length === 1 ? branches[0] : branches.join(', ') || '—';
}

function syncCell(ws) {
  if (ws.excluded || ws.topology === 'none') return '—';
  const syncs = (ws.repos || []).map(r => r.last_sync).filter(Boolean);
  if (!syncs.length) return '—';
  return syncs.sort().pop().slice(0, 16).replace('T', ' ');
}

function rowActions(ws) {
  if (ws.excluded) return '<span style="color:var(--text3);font-size:10px">excluido</span>';
  const name = ws.workspace;
  if (!ws.ok) return '';
  const btns = [];
  if (ws.topology === 'none') {
    btns.push(`<button class="btn sm" onclick="doInit('${name}')">Init git</button>`);
  } else {
    btns.push(`<button class="btn sm primary" onclick="openPush('${name}')">↑ Push</button>`);
    btns.push(`<button class="btn sm" onclick="doPull('${name}')">↓ Pull</button>`);
    btns.push(`<button class="btn sm" onclick="openConfig('${name}')">⚙ Config</button>`);
  }
  return `<div class="row-actions">${btns.join('')}</div>`;
}

function renderTable(data) {
  _data = data;
  const tbody = document.getElementById('ws-tbody');
  if (!data.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:var(--text3);text-align:center;padding:24px">Sin workspaces</td></tr>';
    return;
  }
  tbody.innerHTML = data.map(ws => {
    const excl = ws.excluded ? ' class="excluded"' : '';
    return `<tr${excl}>
      <td><strong>${ws.workspace}</strong></td>
      <td>${statusBadge(ws)}</td>
      <td><div class="repo-chips">${repoChips(ws)}</div></td>
      <td class="hide-sm" style="color:var(--text2);font-size:11px">${githubCell(ws)}</td>
      <td class="hide-sm" style="color:var(--text2);font-size:11px">${branchCell(ws)}</td>
      <td class="hide-sm" style="color:var(--text2);font-size:11px">${syncCell(ws)}</td>
      <td>${rowActions(ws)}</td>
    </tr>`;
  }).join('');
  const n = data.length;
  const ok = data.filter(w => w.ok && !w.excluded && w.topology !== 'none').length;
  document.getElementById('status-bar').innerHTML =
    `<span>${n}</span> workspaces · <span>${ok}</span> con git · última actualización <span>${new Date().toLocaleTimeString()}</span>`;
}

async function refreshAll() {
  document.getElementById('status-bar').textContent = 'Actualizando...';
  const data = await api('/api/list');
  renderTable(data);
}

// ── Init ───────────────────────────────────────────────────────────────────
async function doInit(ws) {
  openDrawer(`
    <h2>Init git <span class="ws-tag">${ws}</span></h2>
    <p style="color:var(--text2);font-size:12px">Inicializará git en <code>${ws}/code/</code></p>
    <div id="log" class="log-box">Esperando...</div>
    <button class="btn primary" id="run-btn" onclick="runInit('${ws}')">▶ Ejecutar</button>
  `);
}

async function runInit(ws) {
  const log = document.getElementById('log');
  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  log.textContent = '';
  appendLog(log, 'info', `Iniciando git en ${ws}/code/…\n`);
  const r = await api(`/api/init/${ws}`, { method: 'POST' });
  if (r.ok) {
    appendLog(log, 'ok', '✓ ' + r.message);
  } else {
    appendLog(log, 'err', '✗ ' + r.message);
  }
  btn.disabled = false;
  refreshAll();
}

// ── Push ───────────────────────────────────────────────────────────────────
function openPush(ws) {
  const wsData = _data.find(w => w.workspace === ws);
  const repos = (wsData?.repos || []);
  const repoOptions = repos.length > 1
    ? `<div class="form-group">
        <label>Repo específico (vacío = todos)</label>
        <select id="push-target">
          <option value="">Todos</option>
          ${repos.map(r => `<option value="${r.name}">${r.name}</option>`).join('')}
        </select>
       </div>`
    : '';
  const now = new Date();
  const defMsg = `sync: ${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

  openDrawer(`
    <h2>Push a GitHub <span class="ws-tag">${ws}</span></h2>
    ${repoOptions}
    <div class="form-group">
      <label>Mensaje del commit</label>
      <input type="text" id="push-msg" value="${defMsg}">
    </div>
    <button class="btn primary" id="run-btn" onclick="runPush('${ws}')">↑ Push</button>
    <div id="log" class="log-box hidden"></div>
  `);
}

async function runPush(ws) {
  const btn = document.getElementById('run-btn');
  const log = document.getElementById('log');
  const msg = document.getElementById('push-msg')?.value || '';
  const target = document.getElementById('push-target')?.value || null;
  btn.disabled = true;
  log.classList.remove('hidden');
  log.textContent = '';
  appendLog(log, 'info', `Enviando ${ws} a GitHub…\n`);

  // Stream SSE
  const params = new URLSearchParams({ msg });
  if (target) params.set('target', target);
  const es = new EventSource(`/api/push/${ws}?${params}`);
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.done) {
      es.close();
      btn.disabled = false;
      refreshAll();
      return;
    }
    const style = d.ok === false ? 'err' : d.ok === true ? 'ok' : 'info';
    appendLog(log, style, d.text + '\n');
  };
  es.onerror = () => {
    es.close();
    appendLog(log, 'err', 'Error de conexión\n');
    btn.disabled = false;
  };
}

// ── Pull ───────────────────────────────────────────────────────────────────
async function doPull(ws) {
  openDrawer(`
    <h2>Pull desde GitHub <span class="ws-tag">${ws}</span></h2>
    <div id="log" class="log-box">Esperando...</div>
    <button class="btn primary" id="run-btn" onclick="runPull('${ws}')">↓ Pull</button>
  `);
}

async function runPull(ws) {
  const log = document.getElementById('log');
  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  log.textContent = '';
  appendLog(log, 'info', `Haciendo pull de ${ws}…\n`);
  const r = await api(`/api/pull/${ws}`, { method: 'POST' });
  (r.repos || []).forEach(rr => {
    const icon = rr.ok ? '✓' : '✗';
    const style = rr.ok ? 'ok' : 'err';
    const detail = rr.output || rr.error || (rr.ok ? 'already up to date' : '');
    appendLog(log, style, `${icon} ${rr.name}  ${detail}\n`);
  });
  if (!r.repos?.length) {
    appendLog(log, r.ok ? 'ok' : 'err', r.message || (r.ok ? 'ok' : 'error'));
  }
  btn.disabled = false;
  refreshAll();
}

// ── Configure ──────────────────────────────────────────────────────────────
function openConfig(ws) {
  const wsData = _data.find(w => w.workspace === ws);
  const repos = (wsData?.repos || []);
  const meta = wsData?.meta || {};

  const repoSelect = repos.length > 1
    ? `<div class="form-group">
        <label>Repo a configurar</label>
        <select id="cfg-target" onchange="updateConfigForm('${ws}')">
          <option value="">Global (todos)</option>
          ${repos.map(r => `<option value="${r.name}">${r.name}</option>`).join('')}
        </select>
       </div>`
    : `<input type="hidden" id="cfg-target" value="">`;

  const firstRepo = repos[0];
  const defName = meta['git.github_repo'] || (firstRepo?.name) || ws;
  const defVis  = meta['git.visibility'] || 'private';

  openDrawer(`
    <h2>Configurar GitHub <span class="ws-tag">${ws}</span></h2>
    ${repoSelect}
    <hr>
    <div class="form-group">
      <label>Nombre del repo en GitHub</label>
      <input type="text" id="cfg-repo-name" value="${defName}" placeholder="nombre-del-repo">
    </div>
    <div class="form-group">
      <label>Visibilidad</label>
      <select id="cfg-visibility">
        <option value="private" ${defVis==='private'?'selected':''}>Private</option>
        <option value="public"  ${defVis==='public' ?'selected':''}>Public</option>
      </select>
    </div>
    <div class="form-group">
      <label>Remote URL (opcional, sobrescribe)</label>
      <input type="text" id="cfg-remote-url" value="${meta['git.remote_url']||''}" placeholder="https://github.com/user/repo.git">
    </div>
    <div id="cfg-result" class="log-box hidden"></div>
    <button class="btn primary" onclick="saveConfig('${ws}')">Guardar</button>
  `);
}

async function saveConfig(ws) {
  const name    = document.getElementById('cfg-repo-name')?.value?.trim() || null;
  const vis     = document.getElementById('cfg-visibility')?.value || null;
  const url     = document.getElementById('cfg-remote-url')?.value?.trim() || null;
  const target  = document.getElementById('cfg-target')?.value || null;
  const result  = document.getElementById('cfg-result');

  const body = {};
  if (name)   body.repo_name  = name;
  if (vis)    body.visibility = vis;
  if (url)    body.remote_url = url;
  if (target) body.target_repo = target;

  const r = await api(`/api/configure/${ws}`, {
    method: 'POST',
    body: JSON.stringify(body),
  });

  result.classList.remove('hidden');
  result.textContent = '';
  appendLog(result, r.ok ? 'ok' : 'err', (r.ok ? '✓ ' : '✗ ') + r.message);
  if (r.ok) refreshAll();
}

// ── Drawer helpers ─────────────────────────────────────────────────────────
function openDrawer(html) {
  document.getElementById('drawer').innerHTML = html;
  document.getElementById('overlay').classList.add('open');
}
function closeDrawer(e) {
  if (!e || e.target === document.getElementById('overlay')) {
    document.getElementById('overlay').classList.remove('open');
  }
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

function appendLog(el, cls, text) {
  const span = document.createElement('span');
  span.className = cls;
  span.textContent = text;
  el.appendChild(span);
  el.scrollTop = el.scrollHeight;
}

// ── Boot ───────────────────────────────────────────────────────────────────
refreshAll();
</script>
</body>
</html>
"""

# ─── API routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return HTML

@app.route("/api/list")
def api_list():
    return jsonify(mgr.list_all())

@app.route("/api/init/<ws>", methods=["POST"])
def api_init(ws: str):
    return jsonify(mgr.init_git(ws))

@app.route("/api/pull/<ws>", methods=["POST"])
def api_pull(ws: str):
    return jsonify(mgr.pull_from_github(ws))

@app.route("/api/configure/<ws>", methods=["POST"])
def api_configure(ws: str):
    body = request.get_json(silent=True) or {}
    return jsonify(mgr.configure_repo(
        ws,
        repo_name=body.get("repo_name"),
        visibility=body.get("visibility"),
        remote_url=body.get("remote_url"),
        target_repo=body.get("target_repo"),
    ))

@app.route("/api/push/<ws>")
def api_push(ws: str):
    """SSE stream para push en tiempo real."""
    target = request.args.get("target") or None
    msg    = request.args.get("msg") or None
    q: queue.Queue = queue.Queue()

    def do_push():
        topo = mgr._detect_git_topology(ws)
        if topo["topology"] == "none":
            q.put({"ok": False, "text": f"✗ No hay repos git en '{ws}'"})
            q.put({"done": True})
            return

        gh_user = mgr._gh_user_login()
        if not gh_user:
            q.put({"ok": False, "text": "✗ gh CLI no autenticado. Ejecuta: gh auth login"})
            q.put({"done": True})
            return

        repos = topo["repos"]
        if target:
            repos = [r for r in repos if r["name"] == target]

        meta = mgr._read_meta(ws)
        commit_msg = msg or f"sync: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}"

        for repo_info in repos:
            q.put({"text": f"→ {repo_info['name']}…"})
            result = mgr._push_single_repo(ws, repo_info, meta, gh_user, commit_msg)
            if result["ok"]:
                action = result.get("action", "pushed")
                q.put({"ok": True, "text": f"✓ {repo_info['name']}  {action}"})
            else:
                q.put({"ok": False, "text": f"✗ {repo_info['name']}  {result.get('error', '')}"})

        q.put({"done": True})

    threading.Thread(target=do_push, daemon=True).start()

    def generate():
        while True:
            item = q.get()
            yield f"data: {json.dumps(item)}\n\n"
            if item.get("done"):
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LAIA git-manager web UI")
    parser.add_argument("--port", type=int, default=5055)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    print(f"\n  LAIA git-manager  →  http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
