"""Render docs/index.html — a self-contained dashboard from the run payload.
Tabs: Signals · Event Studies · Backtests · News & Geopolitics · Desk Note.
"""
from __future__ import annotations

import json
from pathlib import Path

from config import DASH_TITLE


def build(payload: dict, docs: Path) -> Path:
    docs.mkdir(exist_ok=True)
    html = _html(payload)
    out = docs / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def _html(p: dict) -> str:
    data = json.dumps(p, default=str)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{DASH_TITLE}</title>
<style>
:root{{--bg:#f4f6f8;--card:#fff;--ink:#0f172a;--mut:#64748b;--line:#e7ebf0;--soft:#f7f9fb;
 --accent:#0e7c86;--accent-ink:#0b6169;--accent-soft:#e6f4f5;--up:#16a34a;--down:#dc2626;--amber:#d97706}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.55 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-variant-numeric:tabular-nums}}
.wrap{{max-width:1240px;margin:0 auto;padding:0 22px}}
header{{background:color-mix(in srgb,#fff 82%,transparent);backdrop-filter:blur(12px);
 border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20;padding:14px 0}}
.brand{{display:flex;align-items:center;gap:12px}}
.mark{{width:40px;height:40px;border-radius:11px;background:linear-gradient(135deg,var(--accent),var(--accent-ink));
 color:#fff;display:grid;place-items:center;font-weight:800;font-size:17px}}
h1{{font-size:19px;margin:0;font-weight:800;letter-spacing:-.02em}}
.sub{{color:var(--mut);font-size:12.5px}}
.tabs{{display:flex;gap:6px;flex-wrap:wrap;padding:6px;background:#fff;border:1px solid var(--line);
 border-radius:14px;margin:18px 0}}
.tab{{padding:9px 14px;border-radius:10px;font-size:13.5px;font-weight:600;color:var(--mut);
 background:transparent;border:0;cursor:pointer}}
.tab.active{{background:var(--ink);color:#fff}}
.view{{display:none}} .view.active{{display:block;animation:f .25s ease}}
@keyframes f{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1}}}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-bottom:26px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 1px 2px rgba(15,23,42,.04)}}
.card h3{{margin:0 0 2px;font-size:17px}}
.badge{{font-size:11px;font-weight:800;padding:3px 10px;border-radius:999px;color:#fff;text-transform:uppercase;letter-spacing:.03em}}
.b-bull{{background:var(--up)}} .b-bear{{background:var(--down)}} .b-neu{{background:#64748b}}
.row{{display:flex;justify-content:space-between;align-items:baseline;gap:10px}}
.kv{{display:flex;justify-content:space-between;font-size:13px;color:var(--mut);padding:4px 0;border-top:1px solid var(--soft)}}
.kv b{{color:var(--ink)}}
.pill{{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;background:var(--accent-soft);color:var(--accent-ink)}}
.lvl{{display:flex;gap:8px;margin-top:10px}}
.lvl div{{flex:1;background:var(--soft);border:1px solid var(--line);border-radius:9px;padding:7px 9px;text-align:center}}
.lvl .lab{{font-size:10px;color:var(--mut);text-transform:uppercase}} .lvl .val{{font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:9px 10px;text-align:left;border-bottom:1px solid var(--soft);white-space:nowrap}}
th{{background:var(--soft);color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.03em;position:sticky;top:0}}
.panel{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:18px;box-shadow:0 1px 2px rgba(15,23,42,.04)}}
.panel h2{{font-size:16px;margin:0 0 12px}}
.pos{{color:var(--up);font-weight:700}} .neg{{color:var(--down);font-weight:700}}
.spark{{width:100%;height:60px}}
.note{{color:#334155;line-height:1.65}}
.note h2{{font-size:20px;margin:14px 0 6px}} .note h3{{font-size:16px;margin:16px 0 4px}}
.note ul{{margin:6px 0;padding-left:20px}} .note li{{margin:3px 0}}
.news-item{{padding:10px 0;border-top:1px solid var(--soft)}}
.tag{{font-size:10px;font-weight:700;padding:1px 7px;border-radius:6px;margin-right:6px}}
.tag.bull{{background:#e8f7ef;color:var(--up)}} .tag.bear{{background:#fdeae7;color:var(--down)}}
.disc{{color:var(--mut);font-size:11.5px;border-top:1px solid var(--line);padding:18px 0 40px;line-height:1.6}}
@media(max-width:640px){{.tabs{{overflow-x:auto;flex-wrap:nowrap}}}}
</style></head><body>
<header><div class="wrap brand"><div class="mark">CD</div>
 <div><h1>Commodity Desk</h1><div class="sub">Inventory event-studies · backtests · live signals · as of <b id="asof"></b> · <span id="gen"></span></div></div>
</div></header>
<div class="wrap">
 <div class="tabs" id="tabs"></div>
 <div id="v-signals" class="view active"></div>
 <div id="v-study" class="view"></div>
 <div id="v-backtest" class="view"></div>
 <div id="v-news" class="view"></div>
 <div id="v-note" class="view"></div>
 <div class="disc"><b>Educational / research only — not investment advice.</b> Event-studies and
  backtests are hypothetical, computed on historical data with simple assumptions (no slippage/
  roll costs beyond a small fee), and past reactions to reports need not repeat. Inventory data:
  US EIA. Prices: Yahoo Finance. AI notes by Qwen + Llama. Do your own research and manage risk.</div>
</div>
<script>
const D={data};
const el=id=>document.getElementById(id);
el('asof').textContent=D.as_of; el('gen').textContent=D.generated_at||'';
const bcls=v=>v==='Bullish'?'b-bull':v==='Bearish'?'b-bear':'b-neu';
const pc=v=>v==null?'—':(v>=0?'+':'')+v+'%';
const sgn=v=>v==null?'':'class="'+(v>=0?'pos':'neg')+'"';

const TABS=[['signals','Signals'],['study','Event Studies'],['backtest','Backtests'],['news','News & Geopolitics'],['note','Desk Note']];
el('tabs').innerHTML=TABS.map((t,i)=>`<button class="tab ${{i?'':'active'}}" data-t="${{t[0]}}">${{t[1]}}</button>`).join('');
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));
  b.classList.add('active'); el('v-'+b.dataset.t).classList.add('active');
}});

// ---- Signals ----
el('v-signals').innerHTML='<div class="grid">'+D.signals.filter(s=>s.available).map(s=>{{
  const e=s.event_edge||{{}}, L=s.levels||{{}}, st=s.leans_on_stats||{{}};
  return `<div class="card"><div class="row"><h3>${{s.name}}</h3>
    <span class="badge ${{bcls(s.verdict)}}">${{s.verdict}}</span></div>
    <div class="sub">Last <b>${{s.last}}</b> ${{s.unit||''}} · trend ${{s.trend}} · conviction ${{s.conviction}}/3</div>
    <div class="kv"><span>Latest report skew</span><b>${{e.direction||'—'}}</b></div>
    <div class="kv"><span>That signal's hit-rate</span><b>${{e.hit_rate!=null?e.hit_rate+'% ('+(e.count||0)+')':'—'}}</b></div>
    <div class="kv"><span>News tilt</span><b>${{s.news_tilt}} (${{s.news_counts.bullish}}↑/${{s.news_counts.bear||s.news_counts.bearish}}↓)</b></div>
    <div class="kv"><span>Leans on</span><b>${{s.leans_on_strategy||'—'}}</b></div>
    <div class="kv"><span>Edge (CAGR·Sharpe·win)</span><b>${{pc(st.cagr_pct)}} · ${{st.sharpe??'—'}} · ${{st.trade_win_rate_pct??'—'}}%</b></div>
    ${{L.entry?`<div class="lvl"><div><div class="lab">Ref</div><div class="val">${{L.entry}}</div></div>
      <div><div class="lab">Stop</div><div class="val">${{L.stop??'—'}}</div></div>
      <div><div class="lab">Target</div><div class="val">${{L.target??'—'}}</div></div></div>`:''}}
    <p class="sub" style="margin:10px 0 0">${{s.rationale||''}}</p></div>`;
}}).join('')+'</div>';

// ---- Event studies ----
el('v-study').innerHTML=Object.entries(D.commodities).map(([k,c])=>{{
  const bd=(c.study&&c.study.summary&&c.study.summary.by_direction)||{{}};
  const rows=Object.entries(bd).map(([dir,s])=>`<tr><td><b>${{dir}}</b></td><td>${{s.count}}</td>
    <td ${{sgn(s['t+1']&&s['t+1'].avg)}}>${{pc(s['t+1']&&s['t+1'].avg)}}</td>
    <td ${{sgn(s['t+3']&&s['t+3'].avg)}}>${{pc(s['t+3']&&s['t+3'].avg)}}</td>
    <td>${{s.hit_rate!=null?s.hit_rate+'%':'—'}}</td><td>${{s.avg_abs!=null?s.avg_abs+'%':'—'}}</td></tr>`).join('');
  return `<div class="panel"><h2>${{c.name}} <span class="pill">${{c.event}} · ${{c.n_events}} events</span></h2>
    ${{rows?`<table><thead><tr><th>Report skew</th><th>Count</th><th>Avg t+1</th><th>Avg t+3</th><th>Hit-rate t+1</th><th>Avg abs move</th></tr></thead><tbody>${{rows}}</tbody></table>`
      :'<p class="sub">No event data (needs EIA_API_KEY for inventory, or price history for USD-driven metals).</p>'}}</div>`;
}}).join('');

// ---- Backtests ----
function spark(curve){{
  if(!curve||!curve.length) return '';
  const ys=curve.map(p=>p.equity), mn=Math.min(...ys),mx=Math.max(...ys),w=560,h=60;
  const pts=curve.map((p,i)=>`${{(i/(curve.length-1)*w).toFixed(1)}},${{(h-(p.equity-mn)/((mx-mn)||1)*h).toFixed(1)}}`).join(' ');
  const up=ys[ys.length-1]>=ys[0];
  return `<svg class="spark" viewBox="0 0 ${{w}} ${{h}}" preserveAspectRatio="none"><polyline points="${{pts}}" fill="none" stroke="${{up?'#16a34a':'#dc2626'}}" stroke-width="2"/></svg>`;
}}
el('v-backtest').innerHTML=Object.entries(D.commodities).map(([k,c])=>{{
  const bts=c.backtests||{{}};
  const rows=Object.entries(bts).filter(([n,b])=>!b.error).map(([n,b])=>`<tr><td><b>${{n}}</b></td>
    <td ${{sgn(b.total_return_pct)}}>${{pc(b.total_return_pct)}}</td><td ${{sgn(b.cagr_pct)}}>${{pc(b.cagr_pct)}}</td>
    <td>${{b.sharpe}}</td><td class="neg">${{pc(b.max_drawdown_pct)}}</td>
    <td>${{b.trade_win_rate_pct}}%</td><td>${{b.num_trades}}</td></tr>`).join('');
  const best=Object.entries(bts).filter(([n,b])=>!b.error).sort((a,z)=>(z[1].sharpe||-9)-(a[1].sharpe||-9))[0];
  return `<div class="panel"><h2>${{c.name}} — strategy backtests</h2>
    ${{rows?`<table><thead><tr><th>Strategy</th><th>Total</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th><th>Win-rate</th><th>Trades</th></tr></thead><tbody>${{rows}}</tbody></table>
      ${{best?`<div class="sub" style="margin-top:12px">Best by Sharpe — <b>${{best[0]}}</b> equity curve:</div>${{spark(best[1].equity_curve)}}`:''}}`
      :'<p class="sub">No backtest (needs price history / events).</p>'}}</div>`;
}}).join('');

// ---- News ----
el('v-news').innerHTML='<div class="panel"><h2>Commodity &amp; geopolitical news — impact read (Qwen)</h2>'+
 (D.news_all&&D.news_all.length?D.news_all.map(h=>`<div class="news-item">
   ${{h.impact?`<span class="tag ${{h.impact==='bullish'?'bull':h.impact==='bearish'?'bear':''}}">${{(h.commodity||'').toUpperCase()}} ${{h.impact||''}}</span>`:''}}
   <b>${{h.title}}</b> ${{h.why?`<span class="sub">— ${{h.why}}</span>`:''}}
   <div class="sub">${{h.source}}${{h.link?` · <a href="${{h.link}}" target="_blank" rel="noopener">link ↗</a>`:''}}</div></div>`).join('')
  :'<p class="sub">No headlines fetched.</p>')+'</div>';

// ---- Desk note (light markdown) ----
function md(t){{
  return (t||'').split(/\\n/).map(l=>{{
    l=l.replace(/\\*\\*([^*]+)\\*\\*/g,'<b>$1</b>');
    if(/^### /.test(l))return '<h3>'+l.slice(4)+'</h3>';
    if(/^## /.test(l))return '<h2>'+l.slice(3)+'</h2>';
    if(/^[-*] /.test(l))return '<li>'+l.slice(2)+'</li>';
    return l.trim()?'<p>'+l+'</p>':'';
  }}).join('').replace(/(<li>.*?<\\/li>)+/g,m=>'<ul>'+m+'</ul>');
}}
el('v-note').innerHTML='<div class="panel note">'+md(D.desk_note)+'</div>';
</script></body></html>"""
