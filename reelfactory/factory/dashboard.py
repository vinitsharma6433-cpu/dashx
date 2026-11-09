"""DASHX Control Center: a local web page (127.0.0.1 only) to watch and control production. Standard library only.
Shows totals, today's progress, QC/SEO/story scores, bank count, history, upload status, the running job, errors;
buttons for Start, Stop, Retry; and the daily settings. POST calls need the header X-Factory: 1 (blocks cross-site
requests from other web pages). Secrets are never shown: only whether credentials exist."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import ROOT, db, log, ops, youtube
from .bridge import daily, make_stories as ms
from .config import load, save_settings

_gemma = {"v": ("?", ""), "t": 0.0}


def gemma_cached():
    if time.time() - _gemma["t"] > 60:
        _gemma.update(v=daily.gemma_status(), t=time.time())
    return _gemma["v"]


def spawn(args: list[str]) -> int:
    flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    p = subprocess.Popen([sys.executable, "-m", "factory", *args], cwd=ROOT, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.pid


def status() -> dict:
    cfg = load()
    day = time.strftime("%Y-%m-%d")
    st = db.stats()
    today = db.q("SELECT SUM(status='ready') ready, SUM(status='failed') failed, COUNT(*) total FROM jobs WHERE day=?", (day,))[0]
    cur = db.q("SELECT name, stage, started FROM jobs WHERE status='running' ORDER BY id DESC LIMIT 1")
    hist = daily.History(ms.USED)
    bank = sum(1 for b in daily.parse_bank() if b["title_hi"] not in " ".join(hist.recent_titles(500)))
    return {"config": cfg.public(), "stats": st, "today": {k: (v or 0) for k, v in today.items()}, "running": cur[0] if cur else None,
            "lock": ops.lock_info(), "disk": ops.disk(), "bank_left": bank, "bank_total": len(daily.parse_bank()),
            "gemma": gemma_cached()[0], "youtube": youtube.status(cfg), "stop_flag": ops.stop_requested()}


def tail_logs(n: int = 60) -> list[str]:
    f = ROOT / "logs" / f"factory-{time.strftime('%Y%m%d')}.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            j = json.loads(line)
            out.append(f"{j['ts'][11:]} {j['level']:5} {j['event']} {j.get('job', '')}")
        except Exception:
            pass
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode())

    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/":
            self._send(200, PAGE.encode(), "text/html")
        elif path == "/api/status":
            self._json(status())
        elif path == "/api/jobs":
            self._json(db.q("SELECT id,name,day,status,stage,title,source,story_score,qc_score,seo_score,duration_s,repairs,seconds,error FROM jobs ORDER BY id DESC LIMIT 60"))
        elif path == "/api/errors":
            self._json(db.q("SELECT j.name,f.check_id,f.stage,f.detail,f.ts FROM failures f JOIN jobs j ON j.id=f.job_id ORDER BY f.id DESC LIMIT 30"))
        elif path == "/api/uploads":
            self._json(db.q("SELECT j.name,u.status,u.video_id,u.scheduled_at,u.detail FROM uploads u JOIN jobs j ON j.id=u.job_id ORDER BY u.id DESC LIMIT 30"))
        elif path == "/api/logs":
            self._json(tail_logs())
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):  # noqa: N802
        if self.headers.get("X-Factory") != "1":
            return self._json({"error": "missing X-Factory header"}, 403)
        n = int(self.headers.get("Content-Length") or 0)
        data = json.loads(self.rfile.read(n) or b"{}")
        path = self.path.split("?")[0]
        if path == "/api/start":
            if ops.lock_info() and ops.lock_info()["alive"]:
                return self._json({"error": "a run is already active"}, 409)
            args = ["daily"] + ([str(int(data["count"]))] if data.get("count") else []) + (["--source", data["source"]] if data.get("source") in ("auto", "bank", "gemma") else []) + (["--force"] if data.get("force") else [])
            ops.set_stop(False)
            return self._json({"started": True, "pid": spawn(args)})
        if path == "/api/stop":
            ops.set_stop(True)
            return self._json({"stop_requested": True, "note": "the current reel finishes its stage, then production stops"})
        if path == "/api/retry":
            return self._json({"started": True, "pid": spawn(["retry", str(int(data["job_id"]))])})
        if path == "/api/settings":
            clean = {k: v for k, v in data.items() if k != "AUTO_UPLOAD"}
            if "AUTO_UPLOAD" in data:
                if data["AUTO_UPLOAD"] and not youtube.status(load())["client_secret_configured"]:
                    return self._json({"error": "AUTO_UPLOAD stays off: no YouTube credentials are configured"}, 400)
                clean["AUTO_UPLOAD"] = data["AUTO_UPLOAD"]
            return self._json(save_settings(clean).public())
        if path == "/api/feedback":
            db.add_feedback(int(data["job_id"]), int(data["rating"]), str(data.get("note", ""))[:300])
            return self._json({"saved": True})
        self._json({"error": "not found"}, 404)


def serve(port: int = 8765) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # local only, never 0.0.0.0
    log.info(f"dashboard on http://127.0.0.1:{port}")
    print(f"DASHX Control Center: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


PAGE = """<!doctype html><html lang="hi"><head><meta charset="utf-8"><title>DASHX Control Center</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{--bg:#0b1220;--card:#131c31;--ink:#e5e7eb;--mut:#94a3b8;--ok:#22c55e;--bad:#ef4444;--y:#fde047}
@media (prefers-color-scheme:light){:root{--bg:#f1f5f9;--card:#fff;--ink:#0f172a;--mut:#475569}}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,sans-serif}header{padding:14px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{margin:0;font-size:20px;color:var(--y)}main{padding:0 20px 30px;display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.card{background:var(--card);border-radius:12px;padding:14px;overflow:auto}h2{margin:0 0 8px;font-size:14px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
.big{font-size:28px;font-weight:700}.row{display:flex;gap:14px;flex-wrap:wrap}.kv{min-width:90px}.kv span{display:block;color:var(--mut);font-size:12px}
table{width:100%;border-collapse:collapse;font-size:12.5px}td,th{padding:4px 6px;text-align:left;border-bottom:1px solid #8884}th{color:var(--mut)}
button{background:var(--y);color:#111;border:0;border-radius:8px;padding:7px 12px;font-weight:600;cursor:pointer}button.s{background:#8883;color:var(--ink)}
.ok{color:var(--ok)}.bad{color:var(--bad)}.wide{grid-column:1/-1}input,select{background:#8882;color:var(--ink);border:1px solid #8885;border-radius:6px;padding:4px 6px}
pre{margin:0;white-space:pre-wrap;font-size:12px;max-height:260px;overflow:auto}label{display:inline-block;margin:3px 10px 3px 0}
</style></head><body><header><h1>DASHX Control Center</h1><span id="state" class="kv"></span>
<button onclick="start()">Start production</button><button class="s" onclick="stop()">Stop</button><span id="msg"></span></header>
<main>
<div class="card"><h2>Today</h2><div class="row" id="today"></div></div>
<div class="card"><h2>All time</h2><div class="row" id="all"></div></div>
<div class="card"><h2>Current job</h2><div id="cur">idle</div></div>
<div class="card"><h2>System</h2><div id="sys"></div></div>
<div class="card"><h2>Daily settings</h2><div id="cfg"></div><button class="s" onclick="save()">Save settings</button></div>
<div class="card wide"><h2>Production history</h2><table id="jobs"></table></div>
<div class="card"><h2>Upload status</h2><table id="up"></table></div>
<div class="card"><h2>Errors / failed checks</h2><table id="err"></table></div>
<div class="card wide"><h2>Log</h2><pre id="log"></pre></div></main>
<script>
const H={'Content-Type':'application/json','X-Factory':'1'};const $=i=>document.getElementById(i);
const kv=(k,v,c)=>`<div class="kv"><span>${k}</span><b class="big ${c||''}">${v??'-'}</b></div>`;
const get=async u=>(await fetch(u)).json();
async function post(u,b){const r=await fetch(u,{method:'POST',headers:H,body:JSON.stringify(b||{})});const j=await r.json();$('msg').textContent=j.error||j.note||(j.started?'started':'ok');return j}
function start(){post('/api/start',{count:+document.getElementById('c_DAILY_REEL_LIMIT').value,source:document.getElementById('c_SOURCE').value})}
function stop(){post('/api/stop')}function retry(id){post('/api/retry',{job_id:id})}
function save(){const b={};document.querySelectorAll('[id^=c_]').forEach(e=>{const k=e.id.slice(2);b[k]=e.type==='checkbox'?e.checked:e.value});post('/api/settings',b)}
let built=false;
async function tick(){const s=await get('/api/status');
$('state').innerHTML=s.running?'<b class="ok">RUNNING</b>':'<b>idle</b>';
$('today').innerHTML=kv('ready',s.today.ready,'ok')+kv('failed',s.today.failed,s.today.failed?'bad':'')+kv('target',s.config.DAILY_REEL_LIMIT);
$('all').innerHTML=kv('reels',s.stats.total)+kv('ready',s.stats.ready,'ok')+kv('failed',s.stats.failed)+kv('avg QC',s.stats.qc)+kv('avg SEO',s.stats.seo);
$('cur').innerHTML=s.running?`<b>${s.running.name}</b> - stage: ${s.running.stage}`:'idle (no job running)';
$('sys').innerHTML=`bank stories left: <b>${s.bank_left}</b> of ${s.bank_total}<br>Gemma: <b>${s.gemma}</b><br>disk free: ${s.disk.free_gb} GB; ready ${s.disk.ready_mb} MB; backups ${s.disk.backups_mb} MB<br>YouTube: credentials ${s.youtube.client_secret_configured?'set':'<b>not set</b>'}, authorised ${s.youtube.authorised}, AUTO_UPLOAD <b>${s.config.AUTO_UPLOAD}</b>`;
if(!built){built=true;const c=s.config;$('cfg').innerHTML=['DAILY_REEL_LIMIT','MIN_QC_SCORE','MAX_REPAIRS','RUN_TIME'].map(k=>`<label>${k} <input id="c_${k}" value="${c[k]}" size="5"></label>`).join('')+`<label>SOURCE <select id="c_SOURCE">${['auto','bank','gemma'].map(o=>`<option ${o==c.SOURCE?'selected':''}>${o}</option>`).join('')}</select></label><br>`+['AUTO_GENERATE','AUTO_QC','AUTO_REPAIR','AUTO_THUMBNAIL','AUTO_SEO','AUTO_UPLOAD'].map(k=>`<label><input type="checkbox" id="c_${k}" ${c[k]?'checked':''}> ${k}</label>`).join('')}
const j=await get('/api/jobs');$('jobs').innerHTML='<tr><th>id<th>name<th>status<th>stage<th>story<th>QC<th>SEO<th>sec<th>repairs<th>note<th></tr>'+j.map(r=>`<tr><td>${r.id}<td>${r.name}<td class="${r.status=='ready'?'ok':r.status=='failed'?'bad':''}">${r.status}<td>${r.stage}<td>${r.story_score??''}<td>${r.qc_score??''}<td>${r.seo_score??''}<td>${r.seconds?Math.round(r.seconds):''}<td>${r.repairs}<td>${r.error||''}<td>${r.status=='failed'?`<button class=s onclick=retry(${r.id})>Retry</button>`:''}`).join('');
const u=await get('/api/uploads');$('up').innerHTML='<tr><th>name<th>status<th>video<th>when</tr>'+u.map(r=>`<tr><td>${r.name}<td>${r.status}<td>${r.video_id||''}<td>${r.scheduled_at||r.detail||''}`).join('')||'none';
const e=await get('/api/errors');$('err').innerHTML='<tr><th>reel<th>check<th>stage<th>detail</tr>'+e.map(r=>`<tr><td>${r.name}<td>${r.check_id}<td>${r.stage}<td>${r.detail.slice(0,90)}`).join('');
$('log').textContent=(await get('/api/logs')).join('\\n')}
tick();setInterval(tick,3000);
</script></body></html>"""
