/**
 * Simulador do workflow v2: executa os Code nodes reais (extraidos do JSON)
 * e roda cenarios de conversa ponta a ponta.
 * A IA e mockada por stubs que emitem as mesmas tags do prompt real.
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
function runCode(nodeName, staticData, nodeOutputs, inputJson) {
  const src = code[nodeName];
  if (!src) throw new Error(`Code node desconhecido: ${nodeName}`);
  const $getWorkflowStaticData = () => staticData;
  const $input = { all: () => [{ json: inputJson }] };
  const $ = (n) => {
    if (!(n in nodeOutputs)) throw new Error(`Node "${n}" nao executou nesta rodada`);
    return { item: { json: nodeOutputs[n] } };
  };
  const fn = new Function('$getWorkflowStaticData', '$input', '$', src);
  const out = fn($getWorkflowStaticData, $input, $);
  return out && out.length ? out[0].json : null;
}

function rotaEtapa(etapa) {
  if (etapa === 'inicio') return 'Montar Boas-vindas';
  if (etapa === 'aguardando_nome') return 'Salvar Nome e Abrir Conversa';
  if (etapa === 'agente_ia') return 'Preparar Contexto para IA';
  if (etapa === 'encerrado') return 'Mensagem Pos Atendimento';
  return 'Montar Boas-vindas';
}

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
    outs['AI Agent'] = { output: ctx.respostaPronta ? '' : aiStub(ctx, state) };
    saida = runCode('Processar Resposta da IA', state.static, outs, ctx);
    outs['Processar Resposta da IA'] = saida;
  } else {
    saida = runCode(alvo, state.static, outs, sessao);
    outs[alvo] = saida;
  }

  let crm = null, notificou = false;
  if (saida.atendimentoFinalizado) {
    outs['Processar Resposta da IA'] = saida;
    crm = runCode('Montar Payload CRM', state.static, outs, saida).crmPayload;
    notificou = !!saida.qualificado;
  }
  return { node: alvo, msg: saida.message, saida, crm, notificou };
}

// ---------------------------------------------------------------- helpers
const novoState = (phone, pushName) => ({ phone, pushName, static: {} });

let falhas = 0;
function check(desc, cond, extra) {
  console.log(`   [${cond ? '  ok  ' : ' FALHA'}] ${desc}`);
  if (!cond) { falhas++; if (extra !== undefined) console.log('           →', JSON.stringify(extra)); }
}
const head = t => console.log('\n' + '='.repeat(70) + '\n' + t + '\n' + '='.repeat(70));
function show(r) {
  if (r.ignorado) return console.log('   (ignorada)');
  console.log('   Ana: ' + String(r.msg).replace(/\n/g, '\n        '));
}

const RES = 'Paciente com dor cronica, possui prescricao medica. Sem laudo agronomico e sem curso de autocultivo.';

// stubs de IA que emitem as tags reais do prompt
const aiNeutro = () => 'Entendi. Me conta um pouco mais? 🌿';

function aiRoteiro(passos) {
  let i = 0;
  return () => passos[Math.min(i++, passos.length - 1)];
}

// ================================================================ A
head('CENARIO A — Nao existe mais menu numerado');
{
  const st = novoState('5511900000001', 'Maria');
  let r;
  r = turno(st, 'oi', aiNeutro); show(r);
  r = turno(st, 'Maria Souza', aiNeutro); show(r);
  check('nao mostra lista de opcoes numeradas', !/1️⃣|2️⃣|3️⃣|1 -|2 -|3 -/.test(r.msg), r.msg);
  check('faz pergunta aberta', /o que te trouxe/i.test(r.msg), r.msg);
  check('ja vai para o agente de IA', st.static.sessoes['5511900000001'].etapa === 'agente_ia');
}

// ================================================================ B
head('CENARIO B — IA identifica "cliente" pela fala e corta por falta de prescricao');
{
  const st = novoState('5511900000002', 'Ana C');
  const ai = aiRoteiro([
    'Poxa, imagino o quanto isso pesa pra vocês. E o médico dela já chegou a prescrever a Cannabis? 🌿[PERFIL:cliente]',
    'Entendo. A prescrição médica é justamente a base do pedido de HC, então o primeiro passo é procurar um médico prescritor — muitos atendem por telemedicina. Quando tiver em mãos, volta aqui que a gente segue! 💚[PRESCRICAO:nao]\n[RESUMO_INICIO]\nMae busca HC autocultivo para filha com epilepsia. Ainda nao possui prescricao medica. Orientada a procurar medico prescritor.\n[RESUMO_FIM]\n[SEM_PRESCRICAO]',
  ]);
  let r;
  turno(st, 'oi', ai);
  turno(st, 'Ana Clara', ai);

  r = turno(st, 'minha filha tem epilepsia e me falaram do autocultivo', ai); show(r);
  check('classificou como cliente', st.static.sessoes['5511900000002'].perfil === 'cliente',
        st.static.sessoes['5511900000002'].perfil);
  check('preencheu o servico', st.static.sessoes['5511900000002'].servico === 'HC para Autocultivo Medicinal');
  check('tag [PERFIL] removida da msg', !/\[PERFIL/.test(r.msg), r.msg);

  r = turno(st, 'ainda não, o neurologista não quis prescrever', ai); show(r);
  check('encerrou', r.saida.atendimentoFinalizado === true);
  check('NAO qualificado', r.saida.statusLead === 'nao_qualificado', r.saida.statusLead);
  check('advogado NAO notificado', r.notificou === false);
  check('foi para o CRM mesmo assim', !!r.crm);
  check('CRM com prescricaoMedica = Nao', r.crm && r.crm.prescricaoMedica === 'Nao', r.crm);
  check('todas as tags removidas', !/\[(PERFIL|PRESCRICAO|SEM_PRESCRICAO|RESUMO)/.test(r.msg), r.msg);
}

// ================================================================ C
head('CENARIO C — cliente COM prescricao: funil fecha em 3 mensagens');
{
  const st = novoState('5511900000003', 'Joao');
  const ai = aiRoteiro([
    'Entendi, Joao. E você já tem a prescrição médica pra Cannabis? 🌿[PERFIL:cliente]',
    'Ótimo, isso já resolve o principal! Me conta rapidinho: você já tem o laudo agronômico do cultivo e chegou a fazer algum curso de autocultivo? 🌿[PRESCRICAO:sim]',
    'Perfeito, obrigada! Vou encaminhar tudo pra nossa equipe e um especialista fala com você em breve. 🌿\n[RESUMO_INICIO]\n' + RES + '\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
  ]);
  let r, turnosAna = 0;
  turno(st, 'oi', ai);
  turno(st, 'Joao Pedro', ai);

  r = turno(st, 'tenho dor cronica e quero plantar em casa', ai); show(r); turnosAna++;
  check('1a msg ja faz a pergunta de corte', /prescrição/i.test(r.msg), r.msg);

  r = turno(st, 'tenho sim, o médico passou', ai); show(r); turnosAna++;
  check('registrou prescricao = Sim', st.static.sessoes['5511900000003'].prescricao === 'Sim');
  check('2a msg junta laudo + curso numa pergunta só',
        /laudo agronômico/i.test(r.msg) && /curso/i.test(r.msg), r.msg);
  check('2a msg nao fatia em varias perguntas',
        (r.msg.match(/\?/g) || []).length === 1, r.msg);

  r = turno(st, 'não tenho laudo nem fiz curso', ai); show(r); turnosAna++;
  check('fechou na 3a mensagem', turnosAna === 3 && r.saida.atendimentoFinalizado === true);
  check('QUALIFICADO', r.saida.statusLead === 'qualificado');
  check('advogado notificado', r.notificou === true);
  check('CRM com prescricaoMedica = Sim', r.crm && r.crm.prescricaoMedica === 'Sim');
}

// ================================================================ D
head('CENARIO D — IA identifica "palestra" sozinha');
{
  const st = novoState('5511900000004', 'Carla');
  const ai = aiRoteiro([
    'Que legal! Me conta, seria pra qual público? 🎤[PERFIL:palestra]',
    'Perfeito, obrigada! Vou passar pra equipe e alguém te retorna em breve. 🌿\n[RESUMO_INICIO]\nInteresse em palestra para associacao de pacientes, cerca de 80 pessoas. Contato: carla@exemplo.com\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
  ]);
  let r;
  turno(st, 'oi', ai);
  turno(st, 'Carla', ai);
  r = turno(st, 'queria convidar vocês pra uma palestra na minha associação', ai); show(r);
  check('classificou como palestra', st.static.sessoes['5511900000004'].perfil === 'palestra',
        st.static.sessoes['5511900000004'].perfil);

  r = turno(st, 'uns 80 pacientes, meu email é carla@exemplo.com', ai); show(r);
  check('encerrou qualificado', r.saida.qualificado === true);
  check('capturou email', st.static.sessoes['5511900000004'].email === 'carla@exemplo.com',
        st.static.sessoes['5511900000004'].email);
  check('CRM perfil palestra', r.crm && r.crm.perfil === 'palestra', r.crm && r.crm.perfil);
}

// ================================================================ E
head('CENARIO E — IA identifica "profissional" sozinha');
{
  const st = novoState('5511900000005', 'Dra');
  const ai = aiRoteiro([
    'Que bom te receber! Me conta, você já atende com Cannabis ou está começando agora? 🌿[PERFIL:profissional]',
    'Entendi perfeitamente. Vou encaminhar pra nossa equipe e um especialista fala com você. 🌿\n[RESUMO_INICIO]\nVeterinaria em Sorocaba, atende pets com epilepsia. Busca orientacao para prescrever com seguranca juridica.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
  ]);
  let r;
  turno(st, 'oi', ai);
  turno(st, 'Dra. Paula', ai);
  r = turno(st, 'sou veterinária e queria entender como prescrever', ai); show(r);
  check('classificou como profissional', st.static.sessoes['5511900000005'].perfil === 'profissional',
        st.static.sessoes['5511900000005'].perfil);

  r = turno(st, 'atendo pets com epilepsia', ai); show(r);
  check('encerrou qualificado', r.saida.qualificado === true);
  check('CRM perfil profissional', r.crm && r.crm.perfil === 'profissional');
  check('nao mencionou laudo agronomico', !/laudo agronômico/i.test(r.msg));
}

// ================================================================ F
head('CENARIO F — assunto ambiguo: pergunta aberta, nunca lista de opcoes');
{
  const st = novoState('5511900000006', 'X');
  const ai = aiRoteiro(['Claro, posso ajudar! Isso seria pra você mesmo ou pra alguém da família? 🌿']);
  let r;
  turno(st, 'oi', ai);
  turno(st, 'Roberto', ai);
  r = turno(st, 'preciso de uma informação', ai); show(r);
  check('nao ofereceu lista numerada', !/1️⃣|2️⃣|3️⃣/.test(r.msg), r.msg);
  check('perfil segue vazio ate ficar claro', !st.static.sessoes['5511900000006'].perfil);
  check('conversa continua', r.saida.atendimentoFinalizado === false);
}

// ================================================================ G
head('CENARIO G — pedido explicito de advogado');
{
  const st = novoState('5511900000007', 'Pedro');
  turno(st, 'oi', aiNeutro);
  turno(st, 'Pedro', aiNeutro);
  const r = turno(st, 'quero falar com advogado', aiNeutro); show(r);
  check('encerrou qualificado', r.saida.qualificado === true);
  check('advogado notificado', r.notificou === true);
}

// ================================================================ H
head('CENARIO H — valvula de conversa longa + pos-atendimento');
{
  const st = novoState('5511900000008', 'Longa');
  turno(st, 'oi', aiNeutro);
  turno(st, 'Longa', aiNeutro);
  let r, valvula = null;
  for (let i = 0; i < 12 && !valvula; i++) {
    r = turno(st, 'mais um detalhe ' + i, aiNeutro);
    if (r.saida.atendimentoFinalizado) valvula = r;
  }
  show(valvula || r);
  check('encerrou pela valvula', !!valvula);
  check('foi para o advogado', valvula && valvula.notificou === true);

  const depois = turno(st, 'obrigado!', aiNeutro); show(depois);
  check('nao repete boas-vindas', !/Sou a \*Ana\*/.test(depois.msg), depois.msg);
  check('nao reenvia ao CRM', depois.crm === null);
}

// ================================================================ I
head('CENARIO I — "MENU" reinicia o atendimento');
{
  const st = novoState('5511900000009', 'Reset');
  const ai = aiRoteiro(['Certo! 🌿[PERFIL:cliente][PRESCRICAO:sim]']);
  turno(st, 'oi', ai);
  turno(st, 'Reset', ai);
  turno(st, 'quero HC', ai);
  const r = turno(st, 'MENU', ai); show(r);
  check('voltou as boas-vindas', /Sou a \*Ana\*/.test(r.msg));
  check('limpou perfil anterior', !st.static.sessoes['5511900000009'].perfil,
        st.static.sessoes['5511900000009']);
  check('limpou prescricao anterior', !st.static.sessoes['5511900000009'].prescricao);
}

// ================================================================ J
head('CENARIO J — leitura das tags [PERFIL] e [PRESCRICAO]');
{
  const casos = [
    ['[PERFIL:cliente]', 'perfil', 'cliente'],
    ['[PERFIL: palestra ]', 'perfil', 'palestra'],
    ['[PERFIL:profissional]', 'perfil', 'profissional'],
    ['[PERFIL:outro]', 'perfil', 'outro'],
    ['[PRESCRICAO:sim]', 'prescricao', 'Sim'],
    ['[PRESCRICAO:nao]', 'prescricao', 'Nao'],
    ['[PRESCRICAO:não]', 'prescricao', 'Nao'],
  ];
  for (const [tag, campo, esperado] of casos) {
    const tel = '55119' + Math.random().toString().slice(2, 10);
    const st = novoState(tel, 'T');
    const ai = aiRoteiro(['Certo! 🌿' + tag]);
    turno(st, 'oi', ai);
    turno(st, 'T', ai);
    const r = turno(st, 'mensagem qualquer', ai);
    const val = st.static.sessoes[tel][campo];
    check(`${tag} → ${campo}=${esperado}`, val === esperado, `veio "${val}"`);
    check(`   tag removida da msg`, !/\[/.test(r.msg), r.msg);
  }
}

console.log('\n' + '='.repeat(70));
console.log(falhas === 0 ? 'TODOS OS TESTES PASSARAM ✅' : `${falhas} VERIFICACAO(OES) FALHARAM ❌`);
console.log('='.repeat(70));
process.exit(falhas === 0 ? 0 : 1);
