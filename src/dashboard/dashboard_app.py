"""
Dashboard — Painel web de monitoramento da Automação Comercial WhatsApp.

Porta: 50000

Endpoints de página:
    GET /              → dashboard HTML (dark mode, tabs, auto-refresh)

Endpoints de API:
    GET /api/stats
    GET /api/sessions
    GET /api/history          ?inicio=YYYY-MM-DD &fim=YYYY-MM-DD &limit=60
    GET /api/conversas        ?phone= &cod_cli= &inicio= &fim= &limit=200
    GET /api/clientes         ?inicio= &fim= &limit=500

Endpoints de download (via JS fetch → forçam download no browser):
    GET /download/json                   → métricas atuais em JSON
    GET /download/csv                    → métricas atuais em CSV
    GET /download/history/csv            ?inicio= &fim=
    GET /download/conversas/csv          ?phone= &cod_cli= &inicio= &fim=
    GET /download/clientes/csv           ?inicio= &fim=
"""

import csv
import io
import json
import os
from datetime import datetime

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from src.core.history import (
    buscar_clientes_disparados,
    buscar_conversas,
    buscar_historico,
    listar_clientes_com_conversa,
)
from src.core.metrics import obter_stats
from src.core.session_manager import SESSIONS

# ─── App ─────────────────────────────────────────────────────────────────────
dashboard = FastAPI(title="Dashboard — Automação Comercial WhatsApp", version="1.1.0")

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Serve arquivos estáticos (logo.png) da pasta /static/
_STATIC_DIR = os.path.join(_ROOT_DIR, "static")
if os.path.isdir(_STATIC_DIR):
    dashboard.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# ─────────────────────────────────────────────────────────────────────────────
# HTML
# ─────────────────────────────────────────────────────────────────────────────

_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Dashboard — Automação Comercial</title>
  <link rel="icon" href="/static/logo.png" type="image/png"/>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    :root{
      --bg:#0f1117;--bg2:#1a1d27;--bg3:#22263a;--border:#2e3350;
      --accent:#4f8ef7;--accent2:#7c3aed;--green:#22c55e;
      --red:#ef4444;--yellow:#f59e0b;--text:#e2e8f0;--muted:#64748b;
      --r:12px;
    }
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh;padding:20px}

    /* Header */
    .hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px;flex-wrap:wrap;gap:10px}
    .hdr-left{display:flex;align-items:center;gap:12px}
    .logo{height:38px;border-radius:8px;object-fit:contain}
    .logo-fallback{font-size:26px}
    .hdr h1{font-size:20px;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
    .hdr-sub{font-size:11px;color:var(--muted);letter-spacing:.08em}
    .badge{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:999px;font-size:12px;font-weight:500}
    .badge.green{background:rgba(34,197,94,.15);color:var(--green)}
    .dot{width:7px;height:7px;border-radius:50%;background:currentColor;animation:pulse 2s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
    .ri{color:var(--muted);font-size:12px}

    /* Tabs */
    .tabs{display:flex;gap:2px;margin-bottom:20px;border-bottom:1px solid var(--border)}
    .tab{padding:9px 18px;font-size:13px;font-weight:500;cursor:pointer;border-radius:8px 8px 0 0;
         color:var(--muted);border:none;background:transparent;transition:all .2s;font-family:'Inter',sans-serif}
    .tab.active{background:var(--bg2);color:var(--text);border:1px solid var(--border);border-bottom:1px solid var(--bg2);margin-bottom:-1px}
    .tc{display:none}.tc.active{display:block}

    /* Buttons */
    .dbar{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
    .btn{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:8px;font-size:13px;
         font-weight:500;cursor:pointer;text-decoration:none;border:none;transition:all .2s;font-family:'Inter',sans-serif}
    .btn-blue{background:var(--accent);color:#fff}.btn-blue:hover{background:#3b7de8;transform:translateY(-1px)}
    .btn-purple{background:var(--accent2);color:#fff}.btn-purple:hover{background:#6d28d9;transform:translateY(-1px)}
    .btn-green{background:#16a34a;color:#fff}.btn-green:hover{background:#15803d;transform:translateY(-1px)}
    .btn-ghost{background:var(--bg3);color:var(--text);border:1px solid var(--border)}.btn-ghost:hover{background:var(--border)}

    /* Cards */
    .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-bottom:24px}
    .card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:16px;
          position:relative;overflow:hidden;transition:transform .2s,border-color .2s}
    .card:hover{transform:translateY(-2px);border-color:var(--accent)}
    .cl{font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
    .cv{font-size:32px;font-weight:700;line-height:1;margin-bottom:3px}
    .cs{font-size:11px;color:var(--muted)}
    .cb .cv{color:var(--accent)}.cg .cv{color:var(--green)}.cr .cv{color:var(--red)}
    .cy .cv{color:var(--yellow)}.cp .cv{color:var(--accent2)}

    /* Section */
    .st{font-size:14px;font-weight:600;margin-bottom:10px;display:flex;align-items:center;gap:8px}
    .st::after{content:'';flex:1;height:1px;background:var(--border)}

    /* Table */
    .tw{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);overflow:auto;margin-bottom:24px}
    table{width:100%;border-collapse:collapse;font-size:13px}
    thead th{background:var(--bg3);padding:9px 13px;text-align:left;font-size:11px;font-weight:600;
             color:var(--muted);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--border);white-space:nowrap}
    tbody td{padding:9px 13px;border-bottom:1px solid rgba(46,51,80,.35);vertical-align:middle}
    tbody tr:last-child td{border:none}
    tbody tr:hover td{background:var(--bg3)}
    .er td{text-align:center;color:var(--muted);padding:24px}

    /* Chips */
    .chip{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600}
    .chip-cpf{background:rgba(79,142,247,.15);color:var(--accent)}
    .chip-menu{background:rgba(124,58,237,.15);color:var(--accent2)}
    .chip-confirm{background:rgba(245,158,11,.15);color:var(--yellow)}
    .chip-edit{background:rgba(239,68,68,.15);color:var(--red)}
    .chip-ok{background:rgba(34,197,94,.15);color:var(--green)}
    .chip-recv{background:rgba(79,142,247,.12);color:#93c5fd}
    .chip-sent{background:rgba(34,197,94,.12);color:#86efac}

    /* Filter bar */
    .fb{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
    .fb label{font-size:12px;color:var(--muted)}
    .fb input,.fb select{background:var(--bg2);border:1px solid var(--border);color:var(--text);
       padding:7px 11px;border-radius:8px;font-size:12px;font-family:'Inter',sans-serif}
    .fb input:focus,.fb select:focus{outline:none;border-color:var(--accent)}

    /* Metrics side blocks */
    .mrow{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
    .mb{flex:1;min-width:240px;background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:16px}
    .ml{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(46,51,80,.35);font-size:13px}
    .ml:last-child{border:none}
    .mk{color:var(--muted)}.mv{font-weight:600}
    .mv-b{color:var(--accent)}.mv-g{color:var(--green)}.mv-r{color:var(--red)}.mv-y{color:var(--yellow)}

    /* Chat style for conversation */
    .msg-recv{background:var(--bg3);border:1px solid var(--border);border-radius:10px 10px 10px 2px;padding:8px 12px;margin:4px 0;max-width:75%;font-size:13px;word-break:break-word}
    .msg-sent{background:rgba(79,142,247,.15);border:1px solid rgba(79,142,247,.25);border-radius:10px 10px 2px 10px;padding:8px 12px;margin:4px 0;max-width:75%;margin-left:auto;font-size:13px;word-break:break-word}
    .msg-ts{font-size:10px;color:var(--muted);margin-top:2px}
    .chat-wrap{max-height:400px;overflow-y:auto;padding:8px}

    footer{text-align:center;color:var(--muted);font-size:11px;margin-top:24px;padding-top:12px;border-top:1px solid var(--border)}
  </style>
</head>
<body>

<!-- Header -->
<div class="hdr">
  <div class="hdr-left">
    <img src="/static/logo.png" alt="Logo" class="logo" onerror="this.style.display='none';document.getElementById('lf').style.display='block'"/>
    <span class="logo-fallback" id="lf" style="display:none">📱</span>
    <div>
      <div class="hdr-sub">OLINDA DISTRIBUIDORA</div>
      <h1>Automação Comercial WhatsApp</h1>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <span class="badge green"><span class="dot"></span>Serviço Ativo</span>
    <span class="ri">🔄 <b id="cd">30</b>s</span>
  </div>
</div>

<!-- Tabs -->
<div class="tabs">
  <button class="tab active" onclick="showTab('hoje',this)">📊 Execução Atual</button>
  <button class="tab" onclick="showTab('historico',this)">📚 Histórico</button>
  <button class="tab" onclick="showTab('conversas',this)">💬 Conversas</button>
  <button class="tab" onclick="showTab('clientes',this)">👥 Clientes Disparados</button>
</div>

<!-- ══ TAB: HOJE ══ -->
<div id="tab-hoje" class="tc active">
  <div class="dbar">
    <button class="btn btn-blue"   onclick="dl('/download/json')">⬇ JSON Resumo</button>
    <button class="btn btn-purple" onclick="dl('/download/csv')">⬇ CSV Resumo</button>
    <button class="btn btn-ghost"  onclick="loadStats();loadSessions()">🔄 Atualizar</button>
  </div>

  <div class="cards">
    <div class="card cb"><div class="cl">Clientes no Roteiro</div><div class="cv" id="c1">—</div><div class="cs">Última execução</div></div>
    <div class="card cg"><div class="cl">Mensagens Enviadas</div><div class="cv" id="c2">—</div><div class="cs">HTTP 200 ✓</div></div>
    <div class="card cr"><div class="cl">Falhas de Envio</div><div class="cv" id="c3">—</div><div class="cs">Erro Z-API</div></div>
    <div class="card cy"><div class="cl">Sessões Ativas</div><div class="cv" id="c4">—</div><div class="cs">Aguardando resposta</div></div>
    <div class="card cg"><div class="cl">Pedidos Aprovados</div><div class="cv" id="c5">—</div><div class="cs">Confirmados</div></div>
    <div class="card cp"><div class="cl">Telemarketing</div><div class="cv" id="c6">—</div><div class="cs">Encaminhamentos</div></div>
  </div>

  <div class="st">Sessões Ativas</div>
  <div class="tw"><table>
    <thead><tr><th>Telefone</th><th>COD_CLI</th><th>Vendedor</th><th>Estado</th><th>Tent. CPF</th><th>Itens</th><th>Última Atividade</th></tr></thead>
    <tbody id="sb"><tr class="er"><td colspan="7">Carregando...</td></tr></tbody>
  </table></div>

  <div class="st">Detalhes das Métricas</div>
  <div class="mrow">
    <div class="mb">
      <div class="st" style="font-size:12px;margin-bottom:8px">Fluxo Conversacional</div>
      <div class="ml"><span class="mk">Msgs recebidas</span><span class="mv mv-b" id="m1">—</span></div>
      <div class="ml"><span class="mk">Fora da campanha</span><span class="mv mv-y" id="m2">—</span></div>
      <div class="ml"><span class="mk">Erros de CPF</span><span class="mv mv-r" id="m3">—</span></div>
      <div class="ml"><span class="mk">Pedidos cancelados</span><span class="mv mv-r" id="m4">—</span></div>
    </div>
    <div class="mb">
      <div class="st" style="font-size:12px;margin-bottom:8px">Sessões — Histórico</div>
      <div class="ml"><span class="mk">Total criadas</span><span class="mv mv-b" id="m5">—</span></div>
      <div class="ml"><span class="mk">Encerradas normalmente</span><span class="mv mv-g" id="m6">—</span></div>
      <div class="ml"><span class="mk">Encerradas por timeout</span><span class="mv mv-y" id="m7">—</span></div>
      <div class="ml"><span class="mk">Encerradas por CPF</span><span class="mv mv-r" id="m8">—</span></div>
    </div>
    <div class="mb">
      <div class="st" style="font-size:12px;margin-bottom:8px">Timestamps</div>
      <div class="ml"><span class="mk">Serviço iniciado</span><span class="mv" id="m9">—</span></div>
      <div class="ml"><span class="mk">Última execução</span><span class="mv" id="m10">—</span></div>
    </div>
  </div>
</div>

<!-- ══ TAB: HISTÓRICO ══ -->
<div id="tab-historico" class="tc">
  <div class="fb">
    <label>De:</label><input type="date" id="h-ini">
    <label>Até:</label><input type="date" id="h-fim">
    <button class="btn btn-blue" onclick="loadHistorico()">🔍 Filtrar</button>
    <button class="btn btn-ghost" onclick="document.getElementById('h-ini').value='';document.getElementById('h-fim').value='';loadHistorico()">✖ Limpar</button>
    <button class="btn btn-purple" onclick="dlHistCsv()">⬇ CSV do Período</button>
  </div>
  <div class="tw"><table>
    <thead><tr>
      <th>#</th><th>Data</th><th>Hora</th>
      <th>Clientes</th><th>Enviadas</th><th>Falhas</th>
      <th>Sessões</th><th>Pedidos ✓</th><th>Cancelados</th>
      <th>Telemarketing</th><th>CPF Erros</th><th>Timeout</th>
    </tr></thead>
    <tbody id="hb"><tr class="er"><td colspan="12">Carregando...</td></tr></tbody>
  </table></div>
</div>

<!-- ══ TAB: CONVERSAS ══ -->
<div id="tab-conversas" class="tc">
  <div class="fb">
    <label>Telefone:</label>
    <select id="cv-phone" style="min-width:180px"><option value="">— todos —</option></select>
    <label>COD_CLI:</label><input type="text" id="cv-cli" placeholder="ex: 1001" style="width:100px">
    <label>De:</label><input type="date" id="cv-ini">
    <label>Até:</label><input type="date" id="cv-fim">
    <button class="btn btn-blue" onclick="loadConversas()">🔍 Buscar</button>
    <button class="btn btn-green" onclick="dlConvCsv()">⬇ CSV Conversa</button>
  </div>
  <div id="chat-area">
    <div style="text-align:center;color:var(--muted);padding:32px;font-size:13px">
      Selecione um telefone ou clique em Buscar para ver as mensagens.
    </div>
  </div>
</div>

<!-- ══ TAB: CLIENTES DISPARADOS ══ -->
<div id="tab-clientes" class="tc">
  <div class="fb">
    <label>De:</label><input type="date" id="cd-ini">
    <label>Até:</label><input type="date" id="cd-fim">
    <button class="btn btn-blue" onclick="loadClientes()">🔍 Filtrar</button>
    <button class="btn btn-ghost" onclick="document.getElementById('cd-ini').value='';document.getElementById('cd-fim').value='';loadClientes()">✖ Limpar</button>
    <button class="btn btn-green" onclick="dlCliCsv()">⬇ CSV Clientes</button>
  </div>
  <div class="tw"><table>
    <thead><tr>
      <th>Data</th><th>Hora</th><th>Telefone</th>
      <th>COD_CLI</th><th>Vendedor</th><th>CPF/CNPJ</th>
      <th>Última Venda</th><th>Status</th>
    </tr></thead>
    <tbody id="clb"><tr class="er"><td colspan="8">Carregando...</td></tr></tbody>
  </table></div>
</div>

<footer>Automação Comercial Ativa — Olinda Distribuidora &nbsp;|&nbsp; Dashboard v1.1 &nbsp;|&nbsp; <span id="now">—</span></footer>

<script>
/* ── Utilitários ─────────────────────────────────────────────────── */
const fmt = iso => iso ? new Date(iso).toLocaleString('pt-BR') : '—';

function stChip(s){
  const m={
    'Estado.AGUARDANDO_CPF':['chip-cpf','Aguard. CPF'],
    'Estado.AGUARDANDO_MENU':['chip-menu','Menu'],
    'Estado.AGUARDANDO_CONFIRMACAO':['chip-confirm','Confirmar'],
    'Estado.AGUARDANDO_ITEM_EDICAO':['chip-edit','Editar'],
    'Estado.AGUARDANDO_QUANTIDADE':['chip-edit','Qty'],
    'Estado.AGUARDANDO_CONTINUAR_EDICAO':['chip-edit','Cont?'],
    'Estado.ENCERRADA':['chip-ok','Encerrada'],
  };
  const[c,l]=m[s]||['','—'];
  return `<span class="chip ${c}">${l}</span>`;
}

function dl(url){
  const a = document.createElement('a');
  a.href = url;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function buildQs(params){return Object.entries(params).filter(([,v])=>v).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&')}

/* ── TAB: HOJE ─────────────────────────────────────────────────────── */
async function loadStats(){
  const s=(await(await fetch('/api/stats')).json());
  document.getElementById('c1').textContent=s.clientes_encontrados??'—';
  document.getElementById('c2').textContent=s.mensagens_enviadas_ok??'—';
  document.getElementById('c3').textContent=s.mensagens_falhou??'—';
  document.getElementById('c4').textContent=s.sessoes_ativas_agora??'—';
  document.getElementById('c5').textContent=s.pedidos_aprovados??'—';
  document.getElementById('c6').textContent=s.encaminhamentos_telemarketing??'—';
  document.getElementById('m1').textContent=s.mensagens_recebidas??'—';
  document.getElementById('m2').textContent=s.mensagens_fora_campanha??'—';
  document.getElementById('m3').textContent=s.cpf_erros_total??'—';
  document.getElementById('m4').textContent=s.pedidos_cancelados??'—';
  document.getElementById('m5').textContent=s.sessoes_criadas??'—';
  document.getElementById('m6').textContent=s.sessoes_encerradas_ok??'—';
  document.getElementById('m7').textContent=s.sessoes_encerradas_timeout??'—';
  document.getElementById('m8').textContent=s.sessoes_encerradas_cpf??'—';
  document.getElementById('m9').textContent=fmt(s.servico_iniciado_em);
  document.getElementById('m10').textContent=fmt(s.ultima_execucao_diaria);
}

async function loadSessions(){
  const ss=(await(await fetch('/api/sessions')).json());
  const b=document.getElementById('sb');
  if(!ss.length){b.innerHTML='<tr class="er"><td colspan="7">Nenhuma sessão ativa</td></tr>';return}
  b.innerHTML=ss.map(s=>`<tr>
    <td><code>${s.phone}</code></td><td>${s.cod_cli}</td><td>${s.cod_vendedor}</td>
    <td>${stChip(s.estado)}</td>
    <td style="text-align:center">${s.tentativas_cpf}/2</td>
    <td style="text-align:center">${s.itens_pedido}</td>
    <td style="font-size:11px;color:var(--muted)">${fmt(s.ultima_atividade)}</td>
  </tr>`).join('');
}

/* ── TAB: HISTÓRICO ────────────────────────────────────────────────── */
async function loadHistorico(){
  const ini=document.getElementById('h-ini').value, fim=document.getElementById('h-fim').value;
  const qs=buildQs({inicio:ini,fim:fim,limit:60});
  const h=(await(await fetch('/api/history?'+qs)).json());
  const b=document.getElementById('hb');
  if(!h.length){b.innerHTML='<tr class="er"><td colspan="12">Nenhum registro no período</td></tr>';return}
  b.innerHTML=h.map(e=>`<tr>
    <td style="color:var(--muted);font-size:11px">#${e.id}</td>
    <td><b>${e.data_execucao}</b></td><td style="color:var(--muted)">${e.hora_execucao}</td>
    <td style="color:var(--accent);font-weight:600">${e.clientes_encontrados}</td>
    <td style="color:var(--green)">${e.mensagens_enviadas}</td>
    <td style="color:${e.mensagens_falhou>0?'var(--red)':'var(--muted)'}">${e.mensagens_falhou}</td>
    <td>${e.sessoes_criadas}</td>
    <td style="color:var(--green);font-weight:600">${e.pedidos_aprovados}</td>
    <td style="color:${e.pedidos_cancelados>0?'var(--red)':'var(--muted)'}">${e.pedidos_cancelados}</td>
    <td style="color:var(--accent2)">${e.encaminhamentos_telemarketing}</td>
    <td style="color:${e.cpf_erros_total>0?'var(--yellow)':'var(--muted)'}">${e.cpf_erros_total}</td>
    <td style="color:${e.sessoes_encerradas_timeout>0?'var(--yellow)':'var(--muted)'}">${e.sessoes_encerradas_timeout}</td>
  </tr>`).join('');
}

function dlHistCsv(){
  const ini=document.getElementById('h-ini').value, fim=document.getElementById('h-fim').value;
  dl('/download/history/csv?'+buildQs({inicio:ini,fim:fim}));
}

/* ── TAB: CONVERSAS ────────────────────────────────────────────────── */
async function loadPhoneList(){
  const clientes=(await(await fetch('/api/clientes_chat')).json());
  const sel=document.getElementById('cv-phone');
  sel.innerHTML='<option value="">— todos —</option>';
  clientes.forEach(c=>{
    const opt=document.createElement('option');
    opt.value=c.phone;
    opt.textContent=`${c.phone} (COD_CLI: ${c.cod_cli}) — ${c.total_mensagens} msgs`;
    sel.appendChild(opt);
  });
}

async function loadConversas(){
  const phone=document.getElementById('cv-phone').value;
  const cli=document.getElementById('cv-cli').value;
  const ini=document.getElementById('cv-ini').value;
  const fim=document.getElementById('cv-fim').value;
  const qs=buildQs({phone,cod_cli:cli,inicio:ini,fim:fim,limit:200});
  const msgs=(await(await fetch('/api/conversas?'+qs)).json());
  const area=document.getElementById('chat-area');
  if(!msgs.length){
    area.innerHTML='<div style="text-align:center;color:var(--muted);padding:32px;font-size:13px">Nenhuma mensagem encontrada.</div>';
    return;
  }
  const html=msgs.map(m=>{
    const recv=m.direcao==='RECEBIDA';
    const chip=recv?`<span class="chip chip-recv">👤 Cliente</span>`:`<span class="chip chip-sent">🤖 Bot</span>`;
    return `<div style="${recv?'':'display:flex;flex-direction:column;align-items:flex-end'}">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">${chip}
        <span style="font-size:10px;color:var(--muted)">${m.created_at||''}</span>
        <span style="font-size:10px;color:var(--muted)">${m.estado||''}</span>
      </div>
      <div class="${recv?'msg-recv':'msg-sent'}">${(m.mensagem||'').replace(/\n/g,'<br>')}</div>
    </div>`;
  }).join('');
  area.innerHTML=`<div class="chat-wrap">${html}</div>`;
}

function dlConvCsv(){
  const phone=document.getElementById('cv-phone').value;
  const cli=document.getElementById('cv-cli').value;
  const ini=document.getElementById('cv-ini').value;
  const fim=document.getElementById('cv-fim').value;
  const qs=buildQs({phone,cod_cli:cli,inicio:ini,fim:fim});
  dl('/download/conversas/csv?'+qs);
}

/* ── TAB: CLIENTES ─────────────────────────────────────────────────── */
async function loadClientes(){
  const ini=document.getElementById('cd-ini').value, fim=document.getElementById('cd-fim').value;
  const qs=buildQs({inicio:ini,fim:fim,limit:500});
  const rows=(await(await fetch('/api/clientes?'+qs)).json());
  const b=document.getElementById('clb');
  if(!rows.length){b.innerHTML='<tr class="er"><td colspan="8">Nenhum cliente encontrado no período</td></tr>';return}
  b.innerHTML=rows.map(r=>`<tr>
    <td>${r.data_execucao}</td>
    <td style="color:var(--muted);font-size:11px">${r.hora_execucao}</td>
    <td><code>${r.phone}</code></td>
    <td style="color:var(--accent);font-weight:600">${r.cod_cli}</td>
    <td>${r.cod_vendedor}</td>
    <td style="font-size:11px">${r.cpf_cnpj}</td>
    <td style="font-size:11px;color:var(--muted)">${r.dt_ultima_venda}</td>
    <td><span class="chip ${r.status_envio==='OK'?'chip-ok':'chip-edit'}">${r.status_envio}</span></td>
  </tr>`).join('');
}

function dlCliCsv(){
  const ini=document.getElementById('cd-ini').value, fim=document.getElementById('cd-fim').value;
  dl('/download/clientes/csv?'+buildQs({inicio:ini,fim:fim}));
}

/* ── Tabs ──────────────────────────────────────────────────────────── */
let activeTab='hoje';
function showTab(id, btn){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tc').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  btn.classList.add('active');
  activeTab=id;
  if(id==='historico') loadHistorico();
  else if(id==='conversas'){loadPhoneList();loadConversas();}
  else if(id==='clientes') loadClientes();
}

/* ── Auto-refresh ──────────────────────────────────────────────────── */
let secs=30;
setInterval(()=>{
  secs--;
  if(secs<=0){
    secs=30;
    loadStats();loadSessions();
    if(activeTab==='historico') loadHistorico();
    if(activeTab==='clientes')  loadClientes();
  }
  document.getElementById('cd').textContent=secs;
  document.getElementById('now').textContent=new Date().toLocaleString('pt-BR');
},1000);

loadStats();loadSessions();
document.getElementById('now').textContent=new Date().toLocaleString('pt-BR');
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@dashboard.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_HTML)


@dashboard.get("/api/stats")
async def api_stats():
    return JSONResponse(obter_stats())


@dashboard.get("/api/sessions")
async def api_sessions():
    return JSONResponse([
        {
            "phone": phone,
            "cod_cli": sess["cliente"].get("COD_CLI", "N/A"),
            "cod_vendedor": sess["cliente"].get("COD_VENDEDOR", "N/A"),
            "estado": str(sess["state_machine"].obter_estado()),
            "tentativas_cpf": sess["tentativas_cpf"],
            "itens_pedido": len(sess.get("pedido_temp", [])),
            "ultima_atividade": sess["ultima_atividade"].isoformat(),
        }
        for phone, sess in SESSIONS.items()
    ])


@dashboard.get("/api/history")
async def api_history(
    inicio: str = Query(None),
    fim: str = Query(None),
    limit: int = Query(60),
):
    return JSONResponse(buscar_historico(inicio, fim, limit))


@dashboard.get("/api/conversas")
async def api_conversas(
    phone: str = Query(None),
    cod_cli: str = Query(None),
    inicio: str = Query(None),
    fim: str = Query(None),
    limit: int = Query(200),
):
    return JSONResponse(buscar_conversas(phone or None, inicio, fim, cod_cli or None, limit))


@dashboard.get("/api/clientes_chat")
async def api_clientes_chat():
    """Lista clientes únicos que têm conversas registradas (para o select)."""
    return JSONResponse(listar_clientes_com_conversa())


@dashboard.get("/api/clientes")
async def api_clientes(
    inicio: str = Query(None),
    fim: str = Query(None),
    limit: int = Query(500),
):
    return JSONResponse(buscar_clientes_disparados(inicio, fim, limit))


# ─── Downloads ───────────────────────────────────────────────────────────────

def _resposta_download(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@dashboard.get("/download/json")
async def download_json():
    stats = obter_stats()
    stats["gerado_em"] = datetime.now().isoformat()
    content = json.dumps(stats, indent=2, ensure_ascii=False).encode("utf-8")
    return _resposta_download(content, f"metricas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")


@dashboard.get("/download/csv")
async def download_csv():
    stats = obter_stats()
    stats["gerado_em"] = datetime.now().isoformat()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["metrica", "valor"])
    for k, v in stats.items():
        w.writerow([k, v])
    return _resposta_download(out.getvalue().encode("utf-8-sig"),
                              f"metricas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")


@dashboard.get("/download/history/csv")
async def download_history_csv(inicio: str = Query(None), fim: str = Query(None), limit: int = Query(500)):
    dados = buscar_historico(inicio, fim, limit)
    out = io.StringIO()
    if dados:
        w = csv.DictWriter(out, fieldnames=dados[0].keys())
        w.writeheader(); w.writerows(dados)
    return _resposta_download(out.getvalue().encode("utf-8-sig"),
                              f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")


@dashboard.get("/download/conversas/csv")
async def download_conversas_csv(
    phone: str = Query(None),
    cod_cli: str = Query(None),
    inicio: str = Query(None),
    fim: str = Query(None),
    limit: int = Query(500),
):
    dados = buscar_conversas(phone or None, inicio, fim, cod_cli or None, limit)
    out = io.StringIO()
    if dados:
        w = csv.DictWriter(out, fieldnames=dados[0].keys())
        w.writeheader(); w.writerows(dados)
    return _resposta_download(out.getvalue().encode("utf-8-sig"),
                              f"conversa_{phone or 'todos'}_{datetime.now().strftime('%Y%m%d')}.csv")


@dashboard.get("/download/clientes/csv")
async def download_clientes_csv(
    inicio: str = Query(None),
    fim: str = Query(None),
    limit: int = Query(500),
):
    dados = buscar_clientes_disparados(inicio, fim, limit)
    out = io.StringIO()
    if dados:
        w = csv.DictWriter(out, fieldnames=dados[0].keys())
        w.writeheader(); w.writerows(dados)
    return _resposta_download(out.getvalue().encode("utf-8-sig"),
                              f"clientes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
