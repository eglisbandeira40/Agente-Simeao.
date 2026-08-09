# -*- coding: utf-8 -*-
"""Gera um simulador HTML local a partir do workflow v2.

O HTML embute o codigo REAL dos Code nodes e o prompt REAL do AI Agent,
entao testar aqui equivale a testar a logica que vai para o n8n.
"""
import json

WF_PATH = "workflows/Agente_Juridico_Cannabis_v2_SyncHub.json"
OUT = "workflows/simulador_ana.html"

wf = json.load(open(WF_PATH, encoding="utf-8"))

code = {n["name"]: n["parameters"]["jsCode"]
        for n in wf["nodes"] if n["type"] == "n8n-nodes-base.code"}

agent = next(n for n in wf["nodes"] if n["type"].endswith("langchain.agent"))
prompt = agent["parameters"]["options"]["systemMessage"].lstrip("=")

modelo = next(n for n in wf["nodes"] if n["type"].endswith("lmChatAnthropic")
              )["parameters"]["model"]["value"]

mem = next(n for n in wf["nodes"] if n["type"].endswith("memoryPostgresChat"))
janela = mem["parameters"].get("contextWindowLength", 12)

DADOS = json.dumps({"code": code, "prompt": prompt,
                    "modelo": modelo, "janela": janela}, ensure_ascii=False)

HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Simulador — Ana | Simeão Advogados</title>
<style>
  :root{
    --bg:#0f1512; --panel:#18211d; --panel2:#1f2a25; --line:#2c3a33;
    --tx:#e8f0ea; --tx2:#93a79c;
    --verde:#25d366; --verde-esc:#075e54; --bolha-ana:#202c26; --bolha-eu:#075e54;
    --amarelo:#e0b15c; --vermelho:#e06c5c; --azul:#5c9ce0;
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{
    background:var(--bg);color:var(--tx);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    display:flex;flex-direction:column;height:100vh;overflow:hidden;
  }
  code,.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace}

  header{
    background:var(--panel);border-bottom:1px solid var(--line);
    padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;flex:none;
  }
  header h1{font-size:15px;margin:0;font-weight:700;letter-spacing:-.01em}
  header .sub{font-size:11.5px;color:var(--tx2)}
  .cfg{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  input,select,button{font:inherit}
  input[type=password],input[type=text]{
    background:var(--panel2);border:1px solid var(--line);color:var(--tx);
    border-radius:8px;padding:7px 10px;font-size:12.5px;outline:none;
  }
  input:focus{border-color:var(--verde)}
  button{
    background:var(--panel2);border:1px solid var(--line);color:var(--tx);
    border-radius:8px;padding:7px 13px;font-size:12.5px;cursor:pointer;
  }
  button:hover{border-color:var(--verde)}
  button.primary{background:var(--verde-esc);border-color:var(--verde-esc);font-weight:600}
  button:disabled{opacity:.45;cursor:not-allowed}

  main{flex:1;display:grid;grid-template-columns:1fr 380px;min-height:0}
  @media(max-width:900px){main{grid-template-columns:1fr}}

  /* ---------- chat ---------- */
  .chat{display:flex;flex-direction:column;min-height:0;border-right:1px solid var(--line)}
  .msgs{
    flex:1;overflow-y:auto;padding:18px 16px;display:flex;flex-direction:column;gap:8px;
    background:
      radial-gradient(circle at 20% 15%,rgba(37,211,102,.05),transparent 45%),
      radial-gradient(circle at 80% 70%,rgba(224,177,92,.04),transparent 45%),
      var(--bg);
  }
  .b{max-width:74%;padding:8px 12px;border-radius:12px;font-size:13.5px;line-height:1.5;
     white-space:pre-wrap;word-wrap:break-word;position:relative}
  .b.ana{background:var(--bolha-ana);align-self:flex-start;border-bottom-left-radius:3px}
  .b.eu{background:var(--bolha-eu);align-self:flex-end;border-bottom-right-radius:3px}
  .b.sis{align-self:center;background:transparent;border:1px dashed var(--line);
         color:var(--tx2);font-size:11.5px;max-width:88%;text-align:center}
  .b b{font-weight:700}
  .b i{font-style:italic}
  .hora{font-size:10px;color:var(--tx2);opacity:.7;margin-left:8px}

  .digitando{align-self:flex-start;display:flex;gap:4px;padding:11px 14px;
             background:var(--bolha-ana);border-radius:12px;border-bottom-left-radius:3px}
  .digitando i{width:6px;height:6px;border-radius:50%;background:var(--tx2);
               animation:pulsa 1.3s infinite;display:block}
  .digitando i:nth-child(2){animation-delay:.2s}
  .digitando i:nth-child(3){animation-delay:.4s}
  @keyframes pulsa{0%,60%,100%{opacity:.3}30%{opacity:1}}
  @media(prefers-reduced-motion:reduce){.digitando i{animation:none;opacity:.6}}

  .entrada{border-top:1px solid var(--line);background:var(--panel);padding:10px 12px;
           display:flex;gap:8px;flex:none}
  .entrada input{flex:1;border-radius:20px;padding:10px 15px;font-size:13.5px}
  .atalhos{display:flex;gap:6px;padding:0 12px 10px;background:var(--panel);flex-wrap:wrap;flex:none}
  .atalhos button{font-size:11px;padding:4px 10px;border-radius:20px;color:var(--tx2)}

  /* ---------- painel ---------- */
  .painel{overflow-y:auto;background:var(--panel);padding:16px;display:flex;
          flex-direction:column;gap:14px}
  .painel h2{font-size:11px;text-transform:uppercase;letter-spacing:.09em;
             color:var(--tx2);margin:0 0 8px;font-weight:700}
  .card{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:12px}
  .linha{display:flex;justify-content:space-between;gap:10px;font-size:12.5px;
         padding:4px 0;border-bottom:1px solid rgba(255,255,255,.04)}
  .linha:last-child{border-bottom:none}
  .linha span:first-child{color:var(--tx2)}
  .linha span:last-child{font-weight:600;text-align:right;word-break:break-word}
  .pill{display:inline-block;padding:2px 9px;border-radius:20px;font-size:10.5px;font-weight:700}
  .pill.ok{background:rgba(37,211,102,.15);color:var(--verde)}
  .pill.no{background:rgba(224,108,92,.15);color:var(--vermelho)}
  .pill.wait{background:rgba(224,177,92,.15);color:var(--amarelo)}
  .card.crm{border-color:var(--azul)}
  .card.adv{border-color:var(--verde)}
  .card.off{opacity:.4}
  pre.json{margin:8px 0 0;font-size:11px;line-height:1.5;color:var(--tx2);
           white-space:pre-wrap;word-break:break-word;max-height:230px;overflow:auto}
  .aviso{font-size:11.5px;color:var(--amarelo);background:rgba(224,177,92,.09);
         border:1px solid rgba(224,177,92,.3);border-radius:8px;padding:9px 11px;line-height:1.5}
  .erro{font-size:11.5px;color:var(--vermelho);background:rgba(224,108,92,.09);
        border:1px solid rgba(224,108,92,.3);border-radius:8px;padding:9px 11px;line-height:1.5}
  .log{font-size:11px;color:var(--tx2);line-height:1.7}
  .log b{color:var(--tx)}
</style>
</head>
<body>

<header>
  <div>
    <h1>🌿 Simulador — Ana</h1>
    <div class="sub">roda o código real do workflow v2 · nada é enviado ao n8n</div>
  </div>
  <div class="cfg">
    <input type="password" id="chave" placeholder="sua API key da Anthropic (sk-ant-...)" style="width:270px">
    <input type="text" id="modelo" style="width:170px">
    <button id="reiniciar">Reiniciar conversa</button>
  </div>
</header>

<main>
  <section class="chat">
    <div class="msgs" id="msgs"></div>
    <div class="atalhos">
      <button data-t="1">1 · HC autocultivo</button>
      <button data-t="2">2 · Palestra</button>
      <button data-t="3">3 · Profissional</button>
      <button data-t="tenho sim">tenho prescrição</button>
      <button data-t="não tenho">não tenho prescrição</button>
      <button data-t="MENU">MENU</button>
    </div>
    <form class="entrada" id="form">
      <input type="text" id="txt" placeholder="Escreva como se fosse o lead no WhatsApp…" autocomplete="off">
      <button class="primary" type="submit" id="enviar">Enviar</button>
    </form>
  </section>

  <aside class="painel">
    <div id="avisoChave" class="aviso">
      Cole sua <b>API key da Anthropic</b> no campo acima para a Ana responder de verdade.
      A chave fica só no seu navegador e vai apenas para <span class="mono">api.anthropic.com</span>.
      Sem a chave, as etapas fixas (menu, corte de prescrição) ainda funcionam.
    </div>
    <div id="erroBox"></div>

    <div>
      <h2>Estado da sessão</h2>
      <div class="card" id="estado"></div>
    </div>

    <div>
      <h2>Enviar Lead para o CRM (SyncHub)</h2>
      <div class="card crm off" id="cardCrm">
        <div style="font-size:12.5px;color:var(--tx2)">Ainda não disparado.</div>
      </div>
    </div>

    <div>
      <h2>Notificar Advogado</h2>
      <div class="card adv off" id="cardAdv">
        <div style="font-size:12.5px;color:var(--tx2)">Ainda não disparado.</div>
      </div>
    </div>

    <div>
      <h2>Nodes executados</h2>
      <div class="card"><div class="log" id="log">—</div></div>
    </div>
  </aside>
</main>

<script>
const WF = __DADOS__;

/* ================= runtime que imita o n8n ================= */
let estatico = {};
let saidas = {};
let historico = [];   // memoria do chat (equivale ao Postgres Chat Memory)
let trilha = [];

function runCode(nome, inputJson){
  const src = WF.code[nome];
  if(!src) throw new Error('Code node inexistente: '+nome);
  const $getWorkflowStaticData = () => estatico;
  const $input = { all: () => [{ json: inputJson }] };
  const $ = (n) => {
    if(!(n in saidas)) throw new Error('Node "'+n+'" nao executou nesta rodada');
    return { item: { json: saidas[n] } };
  };
  const fn = new Function('$getWorkflowStaticData','$input','$', src);
  const out = fn($getWorkflowStaticData,$input,$);
  trilha.push(nome);
  return (out && out.length) ? out[0].json : null;
}

function rota(etapa){
  if(etapa==='inicio') return 'Montar Boas-vindas';
  if(etapa==='aguardando_nome') return 'Salvar Nome e Enviar Menu';
  if(etapa==='menu') return 'Processar Opcao do Menu';
  if(etapa==='agente_ia') return 'Preparar Contexto para IA';
  if(etapa==='encerrado') return 'Mensagem Pos Atendimento';
  return 'Montar Boas-vindas';
}

/* interpola as expressoes n8n do prompt com os valores reais do contexto */
function montaPrompt(ctx){
  return WF.prompt.replace(
    /\\{\\{\\s*\\$\\('Preparar Contexto para IA'\\)\\.item\\.json\\.(\\w+)\\s*\\}\\}/g,
    (_,campo) => (ctx[campo] ?? '')
  );
}

async function chamaIA(ctx){
  const chave = document.getElementById('chave').value.trim();
  if(!chave){
    return 'Certo, me conta um pouco mais? 🌿\\n\\n(sem API key — resposta simulada)';
  }
  const modelo = document.getElementById('modelo').value.trim() || WF.modelo;
  const msgs = historico.slice(-WF.janela*2).concat([{role:'user',content:ctx.mensagemUsuario}]);

  const r = await fetch('https://api.anthropic.com/v1/messages',{
    method:'POST',
    headers:{
      'content-type':'application/json',
      'x-api-key':chave,
      'anthropic-version':'2023-06-01',
      'anthropic-dangerous-direct-browser-access':'true'
    },
    body:JSON.stringify({
      model:modelo, max_tokens:1024,
      system:montaPrompt(ctx),
      messages:msgs
    })
  });
  if(!r.ok){
    const t = await r.text();
    throw new Error('API '+r.status+': '+t.slice(0,300));
  }
  const d = await r.json();
  return (d.content||[]).filter(c=>c.type==='text').map(c=>c.text).join('').trim();
}

/* ================= um turno completo ================= */
async function turno(texto){
  saidas = {}; trilha = [];
  const agora = Math.floor(Date.now()/1000);
  const gatilho = {
    contacts:[{wa_id:'5511999999999',profile:{name:'Lead Teste'}}],
    messages:[{from:'5511999999999',id:'wamid.'+Math.random(),type:'text',
               timestamp:String(agora),text:{body:texto}}]
  };

  const ext = runCode('Extrair Dados da Mensagem', gatilho);
  if(!ext) return {ignorado:true};
  saidas['Extrair Dados da Mensagem'] = ext;

  const ses = runCode('Buscar Sessao do Usuario', ext);
  saidas['Buscar Sessao do Usuario'] = ses;

  const alvo = rota(ses.etapa);
  let out;

  if(alvo==='Preparar Contexto para IA'){
    const ctx = runCode('Preparar Contexto para IA', ses);
    saidas['Preparar Contexto para IA'] = ctx;

    if(ctx.respostaPronta){
      saidas['AI Agent'] = {output:''};
      trilha.push('(corte deterministico — IA nao chamada)');
    }else{
      const bruta = await chamaIA(ctx);
      saidas['AI Agent'] = {output:bruta};
      historico.push({role:'user',content:ctx.mensagemUsuario});
      historico.push({role:'assistant',content:bruta});
      trilha.push('AI Agent');
    }
    out = runCode('Processar Resposta da IA', ctx);
    saidas['Processar Resposta da IA'] = out;
  }else{
    out = runCode(alvo, ses);
    saidas[alvo] = out;
  }

  let crm=null, advogado=false;
  if(out.atendimentoFinalizado){
    saidas['Processar Resposta da IA'] = out;
    const p = runCode('Montar Payload CRM', out);
    crm = p.crmPayload;
    advogado = !!out.qualificado;
    trilha.push('Enviar Lead para o CRM');
    if(advogado) trilha.push('Notificar Advogado');
  }
  return {out, crm, advogado};
}

/* ================= interface ================= */
const $msgs=document.getElementById('msgs');
const $log=document.getElementById('log');
const $estado=document.getElementById('estado');
const $erro=document.getElementById('erroBox');

function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function wa(s){ // *negrito* e _italico_ do WhatsApp
  return esc(s).replace(/\\*([^*\\n]+)\\*/g,'<b>$1</b>').replace(/_([^_\\n]+)_/g,'<i>$1</i>');
}
function hora(){const d=new Date();return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');}

function bolha(txt,quem){
  const d=document.createElement('div');
  d.className='b '+quem;
  d.innerHTML = quem==='sis' ? esc(txt) : wa(txt)+'<span class="hora">'+hora()+'</span>';
  $msgs.appendChild(d); $msgs.scrollTop=$msgs.scrollHeight;
}
function digitando(on){
  let d=document.getElementById('dig');
  if(on&&!d){
    d=document.createElement('div');d.id='dig';d.className='digitando';
    d.innerHTML='<i></i><i></i><i></i>';
    $msgs.appendChild(d);$msgs.scrollTop=$msgs.scrollHeight;
  }else if(!on&&d) d.remove();
}

function pintaEstado(){
  const s = (estatico.sessoes||{})['5511999999999'] || {};
  const p = s.prescricao ? (s.prescricao==='Sim'
        ? '<span class="pill ok">Sim</span>' : '<span class="pill no">Não</span>')
      : '<span class="pill wait">—</span>';
  const st = s.statusLead==='qualificado' ? '<span class="pill ok">qualificado</span>'
      : s.statusLead==='nao_qualificado' ? '<span class="pill no">não qualificado</span>'
      : '<span class="pill wait">em andamento</span>';
  $estado.innerHTML =
    '<div class="linha"><span>etapa</span><span class="mono">'+esc(s.etapa||'inicio')+'</span></div>'+
    '<div class="linha"><span>nome</span><span>'+esc(s.nome||'—')+'</span></div>'+
    '<div class="linha"><span>perfil</span><span class="mono">'+esc(s.perfil||'—')+'</span></div>'+
    '<div class="linha"><span>serviço</span><span>'+esc(s.servico||'—')+'</span></div>'+
    '<div class="linha"><span>prescrição médica</span><span>'+p+'</span></div>'+
    '<div class="linha"><span>status do lead</span><span>'+st+'</span></div>'+
    '<div class="linha"><span>mensagens</span><span>'+(s.mensagensCount||0)+'</span></div>';
}

function pintaCrm(crm){
  const c=document.getElementById('cardCrm');
  if(!crm){c.className='card crm off';c.innerHTML='<div style="font-size:12.5px;color:var(--tx2)">Ainda não disparado.</div>';return;}
  c.className='card crm';
  c.innerHTML='<div style="font-size:12px;font-weight:700;color:var(--azul);margin-bottom:6px">✓ POST enviado</div>'+
    '<pre class="json">'+esc(JSON.stringify(crm,null,2))+'</pre>';
}
function pintaAdv(on,out){
  const c=document.getElementById('cardAdv');
  if(!on){c.className='card adv off';c.innerHTML='<div style="font-size:12.5px;color:var(--tx2)">Ainda não disparado.</div>';return;}
  c.className='card adv';
  const txt='🌿 *Novo Lead - Simeao Advogados*\\n\\nAtendimento WhatsApp\\n\\n'+
    'Nome: '+(out.nome||'Nao informado')+'\\n'+
    'WhatsApp: '+(out.phone||'Nao informado')+'\\n'+
    'Servico: '+(out.servico||'Nao informado')+'\\n\\n'+
    '📋 *Resumo da conversa:*\\n'+(out.resumo||'Sem resumo registrado')+'\\n\\n'+
    '⚠️ *Entrar em contato o quanto antes!*';
  c.innerHTML='<div style="font-size:12px;font-weight:700;color:var(--verde);margin-bottom:6px">✓ WhatsApp para (11) 94132-1970</div>'+
    '<pre class="json">'+esc(txt)+'</pre>';
}

let ocupado=false;
async function enviar(texto){
  if(ocupado||!texto.trim()) return;
  ocupado=true; document.getElementById('enviar').disabled=true;
  $erro.innerHTML='';
  bolha(texto,'eu');
  digitando(true);
  try{
    const r = await turno(texto);
    digitando(false);
    if(r.ignorado){ bolha('(mensagem ignorada pelo filtro do node Extrair Dados)','sis'); }
    else{
      bolha(r.out.message,'ana');
      pintaCrm(r.crm);
      pintaAdv(r.advogado, r.out);
      if(r.out.atendimentoFinalizado){
        bolha(r.advogado
          ? '● atendimento encerrado — lead QUALIFICADO → CRM + advogado'
          : '● atendimento encerrado — lead NÃO qualificado → só CRM','sis');
      }
    }
    $log.innerHTML = trilha.map(t=>'<b>›</b> '+esc(t)).join('<br>');
  }catch(e){
    digitando(false);
    $erro.innerHTML='<div class="erro"><b>Erro:</b> '+esc(e.message)+'</div>';
  }
  pintaEstado();
  ocupado=false; document.getElementById('enviar').disabled=false;
  document.getElementById('txt').focus();
}

document.getElementById('form').addEventListener('submit',e=>{
  e.preventDefault();
  const i=document.getElementById('txt');
  const v=i.value; i.value='';
  enviar(v);
});
document.querySelectorAll('.atalhos button').forEach(b=>{
  b.addEventListener('click',()=>enviar(b.dataset.t));
});
document.getElementById('reiniciar').addEventListener('click',()=>{
  estatico={};saidas={};historico=[];trilha=[];
  $msgs.innerHTML='';$log.textContent='—';$erro.innerHTML='';
  pintaCrm(null);pintaAdv(false,{});pintaEstado();
  bolha('Conversa reiniciada. Mande qualquer mensagem para a Ana começar.','sis');
});
document.getElementById('chave').addEventListener('input',e=>{
  document.getElementById('avisoChave').style.display = e.target.value.trim()?'none':'block';
});

document.getElementById('modelo').value = WF.modelo;
pintaEstado();
bolha('Mande qualquer mensagem (ex.: "oi") para a Ana iniciar o atendimento.','sis');
</script>
</body>
</html>
"""

html = HTML.replace("__DADOS__", DADOS)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print("OK ->", OUT)
print("code nodes embutidos:", len(code))
print("modelo:", modelo, "| janela de memoria:", janela)
print("tamanho:", round(len(html) / 1024, 1), "KB")
