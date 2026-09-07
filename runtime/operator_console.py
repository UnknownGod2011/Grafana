"""Same-origin operator cockpit assets for the StageGuard API.

The browser never receives Grafana, Gemini, remediation, or infrastructure
credentials. Dynamic values are rendered with DOM text nodes, and no user data is
stored in browser persistence.
"""
from __future__ import annotations

CONSOLE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>StageGuard Operator</title>
  <link rel="stylesheet" href="/assets/operator.css">
</head>
<body>
  <main>
    <header>
      <div><p class="eyebrow">LIVE MEDIA INCIDENT COMMAND</p><h1>StageGuard</h1></div>
      <div id="connection" class="pill">Loading…</div>
    </header>
    <section class="actions" aria-label="Incident controls">
      <button id="refresh">Refresh status</button>
      <button id="investigate" class="primary">Run investigation</button>
      <button id="briefing" disabled>Generate Gemini briefing</button>
    </section>
    <div id="message" role="status" aria-live="polite"></div>
    <section id="empty" class="card"><h2>No active investigation</h2><p>Run a bounded investigation to collect the pinned Grafana evidence plane.</p></section>
    <section id="incident" hidden>
      <div class="grid">
        <article class="card"><p class="label">Incident</p><p id="incident-id" class="mono"></p></article>
        <article class="card"><p class="label">Revision</p><p id="revision" class="mono"></p></article>
        <article class="card"><p class="label">Status</p><p id="status"></p></article>
        <article class="card"><p class="label">Confidence</p><p id="confidence"></p></article>
      </div>
      <article class="card"><h2>Deterministic diagnosis</h2><p id="summary"></p><p><strong>Hypothesis:</strong> <span id="hypothesis"></span></p><p><strong>Production:</strong> <span id="production"></span> · <strong>Feed:</strong> <span id="feed"></span></p></article>
      <article class="card"><h2>Evidence</h2><div class="table-wrap"><table><thead><tr><th>Class</th><th>Value</th><th>Threshold</th><th>Supports</th></tr></thead><tbody id="evidence"></tbody></table></div></article>
      <article id="briefing-card" class="card" hidden><h2>Gemini advisory briefing</h2><p class="notice">Advisory only. It cannot alter incident or remediation state.</p><pre id="briefing-output"></pre></article>
      <article class="card danger-zone"><h2>Revision-bound approval</h2><p>Approval is valid only for the exact evidence revision shown above. Type the full revision to unlock approval.</p><input id="approval-revision" autocomplete="off" spellcheck="false" placeholder="Current revision"><div class="actions"><button id="approve" disabled>Approve remediation</button><button id="execute" disabled>Execute approved action</button></div><p id="approval-state" class="notice"></p></article>
      <article id="recovery-card" class="card" hidden><h2>Recovery verification</h2><pre id="recovery"></pre></article>
    </section>
  </main>
  <script src="/assets/operator.js" defer></script>
</body>
</html>
"""

CONSOLE_CSS = """:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;color-scheme:dark;background:#0b0d10;color:#f4f6f8}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#171b22,#0b0d10 48%);min-height:100vh}main{max-width:1120px;margin:0 auto;padding:32px 20px 64px}header{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:24px}h1{font-size:40px;margin:2px 0}h2{font-size:18px;margin:0 0 12px}.eyebrow,.label{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:#9ca7b5;margin:0}.pill{padding:8px 12px;border:1px solid #39414c;border-radius:999px;font-size:13px}.actions{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 20px}button,input{font:inherit;border-radius:8px;border:1px solid #3a4350;background:#151a21;color:#f4f6f8;padding:10px 14px}button{cursor:pointer}button.primary{background:#f2f4f7;color:#11151a;border-color:#f2f4f7;font-weight:700}button:disabled{opacity:.4;cursor:not-allowed}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.card{background:#11151b;border:1px solid #272e38;border-radius:12px;padding:18px;margin:12px 0;box-shadow:0 12px 28px rgba(0,0,0,.16)}.card p:last-child{margin-bottom:0}.mono,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.mono{font-size:13px;overflow-wrap:anywhere}.notice{color:#aeb8c5;font-size:13px}#message{min-height:24px;color:#f3cb72}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;border-bottom:1px solid #252c35;padding:10px 8px}th{color:#aeb8c5;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0b0e12;border-radius:8px;padding:14px;font-size:13px;line-height:1.5}.danger-zone{border-color:#514327}.danger-zone input{width:min(360px,100%)}@media(max-width:760px){.grid{grid-template-columns:1fr 1fr}header{align-items:flex-start;flex-direction:column}}@media(max-width:460px){.grid{grid-template-columns:1fr}h1{font-size:32px}}
"""

CONSOLE_JS = r"""(() => {
'use strict';
const q = id => document.getElementById(id);
let current = null;
const message = text => { q('message').textContent = text || ''; };
const scalar = value => value === null || value === undefined ? '—' : String(value);
async function request(path, options = {}) {
  const init = {method: options.method || 'GET', headers: {'Accept':'application/json'}, credentials:'same-origin'};
  if (options.body !== undefined) { init.headers['Content-Type']='application/json'; init.body=JSON.stringify(options.body); }
  const response = await fetch(path, init);
  const data = await response.json().catch(() => ({error:'invalid_response', detail:'Server returned a non-JSON response'}));
  if (!response.ok) throw new Error(data.detail || data.error || `Request failed (${response.status})`);
  return data;
}
function renderEvidence(items) {
  const body = q('evidence'); body.replaceChildren();
  (Array.isArray(items) ? items : []).forEach(item => {
    const row = document.createElement('tr');
    [item.evidence_class, item.value, item.threshold, item.supports_hypothesis].forEach(value => {
      const cell = document.createElement('td'); cell.textContent = scalar(value); row.appendChild(cell);
    });
    body.appendChild(row);
  });
}
function render(snapshot) {
  current = snapshot || null;
  q('empty').hidden = !!current; q('incident').hidden = !current;
  q('briefing-card').hidden = true; q('briefing-output').textContent = '';
  q('approval-revision').value = ''; q('approve').disabled = true;
  if (!current) { q('briefing').disabled = true; return; }
  const report = current.report || {};
  q('incident-id').textContent = scalar(current.incident_id); q('revision').textContent = scalar(current.revision);
  q('status').textContent = scalar(report.status); q('confidence').textContent = Number.isFinite(report.confidence) ? `${Math.round(report.confidence*100)}%` : '—';
  q('summary').textContent = scalar(report.summary); q('hypothesis').textContent = scalar(report.hypothesis);
  q('production').textContent = scalar(report.production_id); q('feed').textContent = scalar(report.affected_feed);
  renderEvidence(report.evidence);
  q('briefing').disabled = false;
  const approval = current.approval;
  q('approval-state').textContent = approval ? `Approved for ${scalar(approval.action)} on ${scalar(approval.target)}.` : 'Not approved.';
  q('execute').disabled = !approval || !!current.outcome;
  q('recovery-card').hidden = !current.outcome; q('recovery').textContent = current.outcome ? JSON.stringify(current.outcome, null, 2) : '';
}
async function refresh() { message('Refreshing incident status…'); try { const data=await request('/v1/incident'); render(data.incident); q('connection').textContent='Authenticated'; message(''); } catch(err) { q('connection').textContent='Unavailable'; message(err.message); } }
q('refresh').addEventListener('click', refresh);
q('investigate').addEventListener('click', async () => { message('Collecting bounded Grafana evidence…'); try { const data=await request('/v1/investigate',{method:'POST',body:{}}); render(data.incident); message('Investigation complete.'); } catch(err) { message(err.message); } });
q('briefing').addEventListener('click', async () => { if(!current) return; const binding={incident_id:current.incident_id,revision:current.revision}; message('Generating advisory briefing for this revision…'); try { const data=await request('/v1/briefing',{method:'POST',body:binding}); if(!current || data.revision!==current.revision){message('Briefing discarded because the incident revision changed.');return;} q('briefing-output').textContent=JSON.stringify(data.briefing,null,2); q('briefing-card').hidden=false; message(''); } catch(err) { message(err.message); } });
q('approval-revision').addEventListener('input', event => { q('approve').disabled = !current || event.target.value !== current.revision || current.report?.status !== 'diagnosed'; });
q('approve').addEventListener('click', async () => { if(!current || q('approval-revision').value!==current.revision) return; const binding={incident_id:current.incident_id,revision:current.revision}; if(!window.confirm(`Approve remediation for evidence revision ${current.revision}?`)) return; message('Recording explicit approval…'); try { const data=await request('/v1/approve',{method:'POST',body:binding}); render(data.incident); message('Remediation approved for the current revision.'); } catch(err) { message(err.message); } });
q('execute').addEventListener('click', async () => { if(!current?.approval || current.outcome) return; if(!window.confirm('Execute the already-approved remediation and verify recovery telemetry?')) return; message('Executing approved remediation and verifying recovery…'); try { const data=await request('/v1/execute',{method:'POST',body:{}}); render(data.incident); message('Execution finished; recovery state updated.'); } catch(err) { message(err.message); } });
refresh();
})();
"""
