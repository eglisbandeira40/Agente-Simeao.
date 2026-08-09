/**
 * Simulador do workflow v2: executa os Code nodes reais (extraidos do JSON)
 * e roda cenarios de conversa ponta a ponta.
 * A IA e mockada por um stub controlavel por cenario.
 */
const fs = require('fs');
const path = require('path');

const WF = JSON.parse(fs.readFileSync(
  path.join(__dirname, 'Agente_Juridico_Cannabis_v2_SyncHub.json'), 'utf8'));

const code = {};
for (const n of WF.nodes) {
  if (n.type === 'n8n-nodes-base.code') code[n.name] = n.parameters.jsCode;
}

// ---------------------------------------------------------------- runtime fake
function makeRuntime(staticData, nodeOutputs, inputJson) {
  const $getWorkflowStaticData = () => staticData;
  const $input = { all: () => [{ json: inputJson }] };
  const $ = (nodeName) => {
    if (!(nodeName in nodeOutputs)) {
      throw new Error(`Node "${nodeName}" nao executou nesta rodada`);
    }
    return { item: { json: nodeOutputs[nodeName] } };
  };
  return { $getWorkflowStaticData, $input, $ };
}

function runCode(nodeName, staticData, nodeOutputs, inputJson) {
  const src = code[nodeName];
  if (!src) throw new Error(`Code node desconhecido: ${nodeName}`);
  const { $getWorkflowStaticData, $input, $ } = makeRuntime(staticData, nodeOutputs, inputJson);
  const fn = new Function('$getWorkflowStaticData', '$input', '$', `${src}`);
  const out = fn($getWorkflowStaticData, $input, $);
  return out && out.length ? out[0].json : null;
}

// ---------------------------------------------------------------- switch
function rotaEtapa(etapa) {
  if (etapa === 'inicio') return 'Montar Boas-vindas';
  if (etapa === 'aguardando_nome') return 'Salvar Nome e Enviar Menu';
  if (etapa === 'menu') return 'Processar Opcao do Menu';
  if (etapa === 'agente_ia') return 'Preparar Contexto para IA';
  if (etapa === 'encerrado') return 'Mensagem Pos Atendimento';
  return 'Montar Boas-vindas'; // fallback
}

// ---------------------------------------------------------------- 1 turno
function turno(state, texto, aiStub) {
  const outs = {};
  const now = Math.floor(Date.now() / 1000);

  const trigger = {
    contacts: [{ wa_id: state.phone, profile: { name: state.pushName } }],
    messages: [{ from: state.phone, id: 'wamid.' + Math.random(), type: 'text',
                 timestamp: String(now), text: { body: texto } }],
  };

  const extraido = runCode('Extrair Dados da Mensagem', state.static, outs, trigger);
  if (!extraido) return { ignorado: true };
  outs['Extrair Dados da Mensagem'] = extraido;

  const sessao = runCode('Buscar Sessao do Usuario', state.static, outs, extraido);
  outs['Buscar Sessao do Usuario'] = sessao;

  const alvo = rotaEtapa(sessao.etapa);
  let saida;

  if (alvo === 'Preparar Contexto para IA') {
    const ctx = runCode('Preparar Contexto para IA', state.static, outs, sessao);
    outs['Preparar Contexto para IA'] = ctx;

    if (ctx.respostaPronta) {
      outs['AI Agent'] = { output: '' };
    } else {
      outs['AI Agent'] = { output: aiStub(ctx, state) };
    }
    saida = runCode('Processar Resposta da IA', state.static, outs, ctx);
    outs['Processar Resposta da IA'] = saida;
  } else {
    saida = runCode(alvo, state.static, outs, sessao);
    outs[alvo] = saida;
  }

  // ramo pos envio ao cliente
  let crm = null, notificou = false;
  if (saida.atendimentoFinalizado) {
    outs['Processar Resposta da IA'] = saida;
    const pay = runCode('Montar Payload CRM', state.static, outs, saida);
    crm = pay.crmPayload;
    notificou = !!saida.qualificado;
  }

  return { node: alvo, msg: saida.message, saida, crm, notificou };
}

// ---------------------------------------------------------------- helpers
function novoState(phone, pushName) {
  return { phone, pushName, static: {} };
}

let falhas = 0;
function check(desc, cond, extra) {
  const tag = cond ? '  ok  ' : ' FALHA';
  console.log(`   [${tag}] ${desc}`);
  if (!cond) { falhas++; if (extra !== undefined) console.log('           →', JSON.stringify(extra)); }
}

function head(t) { console.log('\n' + '='.repeat(70) + '\n' + t + '\n' + '='.repeat(70)); }
function show(r) {
  if (r.ignorado) { console.log('   (mensagem ignorada)'); return; }
  console.log('   Ana: ' + String(r.msg).replace(/\n/g, '\n        '));
}

// ---------------------------------------------------------------- stubs de IA
const aiSilencioso = () => 'Certo, me conta um pouco mais? 🌿';

function aiConcluiApos(nTrocas, resumo) {
  let c = 0;
  return () => {
    c++;
    if (c < nTrocas) return 'Entendi. Pode me contar um pouco mais sobre isso? 🌿';
    return `Obrigada por compartilhar! Vou encaminhar tudo pra nossa equipe e um especialista fala com você em breve. 🌿\n\n[RESUMO_INICIO]\n${resumo}\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]`;
  };
}

const aiSemPrescricao = () =>
  'Entendo. A prescrição médica é a base do pedido de HC, então o primeiro passo é procurar um médico prescritor. Quando tiver, volta aqui! 💚\n\n[RESUMO_INICIO]\nLead busca HC autocultivo mas nao possui prescricao medica. Orientado a procurar medico prescritor.\n[RESUMO_FIM]\n[SEM_PRESCRICAO]';

// ================================================================ CENARIO A
head('CENARIO A — Opcao 1 SEM prescricao medica (corte deterministico)');
{
  const st = novoState('5511900000001', 'Maria');
  let r;
  r = turno(st, 'oi', aiSilencioso); show(r);
  r = turno(st, 'Maria Souza', aiSilencioso); show(r);
  r = turno(st, '1', aiSilencioso); show(r);
  check('pergunta a prescricao de forma natural (sem "1 - Sim")',
        /prescrição médica/i.test(r.msg) && !/1 - Sim/.test(r.msg), r.msg);

  r = turno(st, 'não tenho', aiSilencioso); show(r);
  check('encerrou o atendimento', r.saida.atendimentoFinalizado === true);
  check('marcou como NAO qualificado', r.saida.statusLead === 'nao_qualificado', r.saida.statusLead);
  check('NAO notificou o advogado', r.notificou === false);
  check('enviou o lead para o CRM mesmo assim', !!r.crm);
  check('CRM recebeu prescricaoMedica = Nao', r.crm && r.crm.prescricaoMedica === 'Nao', r.crm);
  check('orientou a providenciar a prescricao', /médico prescritor/i.test(r.msg));
}

// ================================================================ CENARIO B
head('CENARIO B — Opcao 1 COM prescricao (conversa livre + resumo p/ advogado)');
{
  const st = novoState('5511900000002', 'Joao');
  const ai = aiConcluiApos(3, 'Paciente com dor cronica, possui prescricao medica. Nao tem laudo agronomico nem curso de autocultivo. Quer entrar com HC o quanto antes.');
  let r;
  turno(st, 'oi', ai);
  turno(st, 'Joao Pedro', ai);
  r = turno(st, '1', ai); show(r);

  r = turno(st, 'tenho sim', ai); show(r);
  check('nao encerrou ainda (conversa segue livre)', r.saida.atendimentoFinalizado === false);
  check('registrou prescricao = Sim', st.static.sessoes['5511900000002'].prescricao === 'Sim');

  r = turno(st, 'tenho dor cronica ha anos e uso oleo', ai); show(r);
  check('segue conversando', r.saida.atendimentoFinalizado === false);

  r = turno(st, 'nao tenho laudo agronomico e nunca fiz curso', ai); show(r);
  check('encerrou o atendimento', r.saida.atendimentoFinalizado === true);
  check('marcou como QUALIFICADO', r.saida.statusLead === 'qualificado', r.saida.statusLead);
  check('notificou o advogado', r.notificou === true);
  check('enviou para o CRM', !!r.crm);
  check('resumo chegou preenchido', r.crm && r.crm.resumoConversa.length > 30, r.crm && r.crm.resumoConversa);
  check('tags removidas da msg ao cliente',
        !/\[ATENDIMENTO_CONCLUIDO\]|\[RESUMO_INICIO\]/.test(r.msg), r.msg);
}

// ================================================================ CENARIO C
head('CENARIO C — Opcao 2 (palestra) conversa livre');
{
  const st = novoState('5511900000003', 'Carla');
  const ai = aiConcluiApos(2, 'Interesse em palestra para uma associacao de pacientes, cerca de 80 pessoas, previsao para outubro. Contato: carla@exemplo.com');
  let r;
  turno(st, 'oi', ai);
  turno(st, 'Carla', ai);
  r = turno(st, '2', ai); show(r);
  check('mensagem de palestra sem checklist', /palestra/i.test(r.msg));

  r = turno(st, 'é pra uma associacao de pacientes', ai); show(r);
  r = turno(st, 'meu email é carla@exemplo.com', ai); show(r);
  check('encerrou', r.saida.atendimentoFinalizado === true);
  check('qualificado', r.saida.qualificado === true);
  check('capturou o email na sessao', st.static.sessoes['5511900000003'].email === 'carla@exemplo.com',
        st.static.sessoes['5511900000003'].email);
  check('CRM com perfil palestra', r.crm && r.crm.perfil === 'palestra', r.crm && r.crm.perfil);
}

// ================================================================ CENARIO D
head('CENARIO D — Opcao 3 (profissional de saude)');
{
  const st = novoState('5511900000004', 'Dr Silva');
  const ai = aiConcluiApos(2, 'Medico neurologista em Campinas, atende pacientes com epilepsia refrataria. Busca orientacao para prescrever com seguranca juridica.');
  let r;
  turno(st, 'oi', ai);
  turno(st, 'Dr. Silva', ai);
  r = turno(st, '3', ai); show(r);
  r = turno(st, 'sou neurologista em campinas', ai); show(r);
  r = turno(st, 'quero saber como prescrever com seguranca', ai); show(r);
  check('encerrou', r.saida.atendimentoFinalizado === true);
  check('qualificado', r.saida.qualificado === true);
  check('notificou advogado', r.notificou === true);
  check('CRM perfil profissional', r.crm && r.crm.perfil === 'profissional', r.crm && r.crm.perfil);
  check('NAO perguntou laudo agronomico p/ profissional',
        !/laudo agronômico/i.test(r.msg));
}

// ================================================================ CENARIO E
head('CENARIO E — Opcao invalida no menu');
{
  const st = novoState('5511900000005', 'Teste');
  turno(st, 'oi', aiSilencioso);
  turno(st, 'Teste', aiSilencioso);
  const r = turno(st, 'blablabla', aiSilencioso); show(r);
  check('repetiu o menu', /1️⃣/.test(r.msg));
  check('nao finalizou atendimento', !r.saida.atendimentoFinalizado);
}

// ================================================================ CENARIO F
head('CENARIO F — Lead pede para falar com advogado');
{
  const st = novoState('5511900000006', 'Pedro');
  const ai = aiSilencioso;
  turno(st, 'oi', ai);
  turno(st, 'Pedro', ai);
  turno(st, '1', ai);
  turno(st, 'tenho sim', ai);
  const r = turno(st, 'quero falar com advogado', ai); show(r);
  check('encerrou', r.saida.atendimentoFinalizado === true);
  check('qualificado', r.saida.qualificado === true);
  check('notificou advogado', r.notificou === true);
}

// ================================================================ CENARIO G
head('CENARIO G — Valvula de seguranca (conversa muito longa)');
{
  const st = novoState('5511900000007', 'Longa');
  const ai = aiSilencioso;
  turno(st, 'oi', ai);
  turno(st, 'Longa', ai);
  turno(st, '1', ai);
  turno(st, 'tenho sim', ai);
  let r, valvula = null;
  for (let i = 0; i < 12 && !valvula; i++) {
    r = turno(st, 'mais um detalhe ' + i, ai);
    if (r.saida.atendimentoFinalizado) valvula = r;
  }
  show(valvula || r);
  check('encerrou pela valvula', !!valvula);
  check('foi para o advogado', valvula && valvula.notificou === true);

  const depois = turno(st, 'obrigado!', ai); show(depois);
  check('pos-atendimento nao repete boas-vindas', !/Sou a \*Ana\*/.test(depois.msg), depois.msg);
  check('pos-atendimento nao reenvia ao CRM', depois.crm === null);
}

// ================================================================ CENARIO H
head('CENARIO H — "MENU" reseta a sessao');
{
  const st = novoState('5511900000008', 'Reset');
  turno(st, 'oi', aiSilencioso);
  turno(st, 'Reset', aiSilencioso);
  turno(st, '1', aiSilencioso);
  turno(st, 'não tenho', aiSilencioso);
  const r = turno(st, 'MENU', aiSilencioso); show(r);
  check('voltou para as boas-vindas', /Sou a \*Ana\*/.test(r.msg));
  check('limpou a prescricao anterior',
        !st.static.sessoes['5511900000008'].prescricao,
        st.static.sessoes['5511900000008']);
}

// ================================================================ CENARIO I
head('CENARIO I — Variacoes naturais de resposta sobre prescricao');
{
  const casos = [
    ['tenho sim', 'Sim'], ['já tenho', 'Sim'], ['possuo', 'Sim'], ['1', 'Sim'],
    ['sim, o médico passou', 'Sim'],
    ['não tenho', 'Nao'], ['ainda não', 'Nao'], ['nao', 'Nao'], ['2', 'Nao'],
    ['ainda não consegui', 'Nao'], ['sem prescrição', 'Nao'],
  ];
  for (const [txt, esperado] of casos) {
    const st = novoState('551190000900' + Math.random().toString().slice(2, 6), 'X');
    turno(st, 'oi', aiSilencioso);
    turno(st, 'X', aiSilencioso);
    turno(st, '1', aiSilencioso);
    turno(st, txt, aiSilencioso);
    const p = Object.values(st.static.sessoes)[0].prescricao;
    check(`"${txt}" → ${esperado}`, p === esperado, `classificou como "${p}"`);
  }
}

// ---------------------------------------------------------------- resultado
console.log('\n' + '='.repeat(70));
if (falhas === 0) console.log('TODOS OS TESTES PASSARAM ✅');
else console.log(`${falhas} VERIFICACAO(OES) FALHARAM ❌`);
console.log('='.repeat(70));
process.exit(falhas === 0 ? 0 : 1);
