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

  let crm = null, notificou = false, aviso = null;
  if (saida.atendimentoFinalizado) {
    outs['Processar Resposta da IA'] = saida;
    crm = runCode('Montar Payload CRM', state.static, outs, saida).crmPayload;
    notificou = !!saida.qualificado;
    if (notificou) {
      const av = runCode('Montar Aviso do Advogado', state.static, outs, saida);
      aviso = av.waBody;
    }
  }
  return { node: alvo, msg: saida.message, saida, crm, notificou, aviso };
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

// ================================================================ K
head('CENARIO K — TRAVA: IA tenta fechar sem ter perguntado a prescricao');
{
  const st = novoState('5511900000011', 'Bavio');
  // simula exatamente o bug: IA identifica cliente e ja tenta encerrar inventando dados
  const ai = aiRoteiro([
    'Olá! Essa autorização é para uso pessoal ou de um familiar? 🌿[PERFIL:cliente]',
    'Perfeito, vou encaminhar pro nosso time! 🌿\n[RESUMO_INICIO]\nBusca HC autocultivo. Possui prescricao medica e laudo agronomico.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
  ]);
  let r;
  turno(st, 'oi', ai);
  turno(st, 'bavio', ai);
  r = turno(st, 'quro saber como funiona para obter o uso', ai); show(r);
  check('identificou cliente', st.static.sessoes['5511900000011'].perfil === 'cliente');

  r = turno(st, 'para so', ai); show(r);
  check('TRAVA: nao encerrou sem prescricao', r.saida.atendimentoFinalizado === false, r.saida);
  check('TRAVA: nao notificou advogado', r.notificou === false);
  check('TRAVA: nao mandou pro CRM', r.crm === null);
  check('TRAVA: pergunta a prescricao', /prescrição médica/i.test(r.msg), r.msg);
  check('TRAVA: resumo inventado descartado', !r.saida.resumo, r.saida.resumo);
}

// ================================================================ L
head('CENARIO L — TRAVA: IA tenta fechar sem ter identificado o perfil');
{
  const st = novoState('5511900000012', 'Vago');
  const ai = aiRoteiro([
    'Certo, vou encaminhar! 🌿\n[RESUMO_INICIO]\nLead quer informacoes.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
  ]);
  turno(st, 'oi', ai);
  turno(st, 'Vago', ai);
  const r = turno(st, 'preciso de uma informacao', ai); show(r);
  check('TRAVA: nao encerrou sem perfil', r.saida.atendimentoFinalizado === false);
  check('TRAVA: nao notificou advogado', r.notificou === false);
  check('TRAVA: pede para direcionar', /profissional de saúde/i.test(r.msg), r.msg);
}

// ================================================================ M
head('CENARIO M — TRAVA libera quando os dados obrigatorios existem');
{
  const st = novoState('5511900000013', 'Ok');
  const ai = aiRoteiro([
    'Entendi! E você já tem a prescrição médica? 🌿[PERFIL:cliente]',
    'Ótimo! Vou encaminhar pro nosso time. 🌿[PRESCRICAO:sim]\n[RESUMO_INICIO]\nBusca HC autocultivo, uso proprio. Prescricao medica: sim. Laudo agronomico: nao informado. Curso: nao informado.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
  ]);
  turno(st, 'oi', ai);
  turno(st, 'Ok', ai);
  turno(st, 'quero HC pra uso proprio', ai);
  const r = turno(st, 'tenho sim', ai); show(r);
  check('encerrou normalmente', r.saida.atendimentoFinalizado === true);
  check('qualificado', r.saida.qualificado === true);
  check('advogado notificado', r.notificou === true);
  check('resumo usa "nao informado"', /nao informado/i.test(r.crm.resumoConversa), r.crm.resumoConversa);
}

// ================================================================ N
head('CENARIO N — nao repete saudacao nem se reapresenta');
{
  const casos = [
    ['Olá, Eglis! Aqui é a Ana, do Escritório José Simeão — fico feliz em te ajudar 🌿\n\nMe conta rapidinho: é pra você ou pra alguém da família?',
     'saudacao + apresentacao completa'],
    ['Oi Eglis! Sou a Ana do escritório. Como posso ajudar?', 'oi + sou a ana'],
    ['Aqui é a Ana. Me conta mais sobre o caso?', 'apresentacao sem saudacao'],
  ];
  for (const [bruta, desc] of casos) {
    const tel = '55119' + Math.random().toString().slice(2, 10);
    const st = novoState(tel, 'T');
    const ai = aiRoteiro([bruta]);
    turno(st, 'oi', ai);
    turno(st, 'Eglis', ai);
    const r = turno(st, 'quero saber como funciona', ai);
    check(`limpa "${desc}"`, !/aqui [eé] a ana|sou a ana/i.test(r.msg), r.msg);
  }
}

// ================================================================ O
head('CENARIO O — quem entra em contato e o Dr. Jose Simeao');
{
  const st = novoState('5511900000014', 'Pedro');
  turno(st, 'oi', aiNeutro);
  turno(st, 'Pedro', aiNeutro);
  const r = turno(st, 'quero falar com advogado', aiNeutro); show(r);
  check('cita Dr. José Simeão', /Dr\. José Simeão/.test(r.msg), r.msg);
  check('nao diz "especialista"', !/especialista/i.test(r.msg), r.msg);
  check('nao diz "nossa equipe"', !/nossa equipe/i.test(r.msg), r.msg);
}

// ================================================================ P
head('CENARIO P — lead lacônico nao arrasta a conversa (teto de 5 turnos da IA)');
{
  const st = novoState('5511900000015', 'Eglis');
  // IA sempre pedindo esclarecimento, como aconteceu no teste real
  const ai = aiRoteiro(['Me conta um pouquinho mais sobre isso? 🌿']);
  turno(st, 'ola', ai);
  turno(st, 'eglis', ai);

  const vagos = ['quero saber mais', 'para outra finalidade', 'outra coisa',
                 'regulamentacao', 'normas', 'sei la', 'talvez'];
  let r, fim = null, turnos = 0;
  for (const v of vagos) {
    if (fim) break;
    r = turno(st, v, ai); turnos++;
    if (r.saida.atendimentoFinalizado) fim = r;
  }
  show(fim || r);
  check('encerrou sozinho', !!fim);
  check('encerrou em no maximo 6 trocas', turnos <= 6, `levou ${turnos}`);
  check('encaminhou ao advogado', fim && fim.notificou === true);
  check('cita Dr. José Simeão', fim && /Dr\. José Simeão/.test(fim.msg), fim && fim.msg);
  check('resumo admite o que nao foi informado',
        fim && /nao informado/i.test(fim.crm.resumoConversa), fim && fim.crm.resumoConversa);
  check('resumo nao inventa que possui algo',
        fim && !/possui (prescricao|laudo)/i.test(fim.crm.resumoConversa), fim && fim.crm.resumoConversa);
}

// ================================================================ Q
head('CENARIO Q — conversa normal nao e afetada pelo teto');
{
  const st = novoState('5511900000016', 'Rapido');
  const ai = aiRoteiro([
    'Entendi! E você já tem a prescrição médica? 🌿[PERFIL:cliente]',
    'Ótimo! Já tem laudo agronômico e fez algum curso de autocultivo? 🌿[PRESCRICAO:sim]',
    'Perfeito, obrigada! O Dr. José Simeão fala com você em breve. 🌿\n[RESUMO_INICIO]\nBusca HC autocultivo. Prescricao: sim. Laudo: nao. Curso: nao.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
  ]);
  turno(st, 'oi', ai);
  turno(st, 'Rapido', ai);
  turno(st, 'quero HC pra uso proprio', ai);
  turno(st, 'tenho sim', ai);
  const r = turno(st, 'nao tenho nenhum dos dois', ai); show(r);
  check('fechou pelo caminho normal (3 turnos)', r.saida.atendimentoFinalizado === true);
  check('qualificado', r.saida.qualificado === true);
  check('resumo veio da IA, nao do teto',
        !/encerrada automaticamente/i.test(r.crm.resumoConversa), r.crm.resumoConversa);
}

// ================================================================ R
head('CENARIO R — profissional de saude de qualquer nicho qualifica sem prescricao');
{
  const nichos = [
    ['sou nutricionista e quero orientar meus pacientes', 'nutricionista'],
    ['sou psicologa, atendo pacientes com ansiedade', 'psicologa'],
    ['sou farmaceutico de manipulacao', 'farmaceutico'],
    ['sou enfermeira em cuidados paliativos', 'enfermeira'],
    ['sou veterinaria', 'veterinaria'],
  ];
  for (const [fala, nicho] of nichos) {
    const tel = '55119' + Math.random().toString().slice(2, 10);
    const st = novoState(tel, 'Prof');
    const ai = aiRoteiro([
      'Que bom! Me conta sua área e o que você busca? 🌿[PERFIL:profissional]',
      'Perfeito! O Dr. José Simeão fala com você em breve. 🌿\n[RESUMO_INICIO]\nProfissional de saude (' + nicho + ') busca consultoria.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
    ]);
    turno(st, 'oi', ai);
    turno(st, 'Prof', ai);
    turno(st, fala, ai);
    const r = turno(st, 'quero consultoria', ai);
    check(`${nicho}: qualificou sem prescricao`,
          r.saida.qualificado === true && r.saida.atendimentoFinalizado === true, r.saida.statusLead);
    check(`${nicho}: nao foi barrado pela trava`, !/prescrição médica/i.test(r.msg), r.msg);
  }
}

// ================================================================ S
head('CENARIO S — palestra qualifica sem requisito nenhum');
{
  const st = novoState('5511900000017', 'Palestra');
  const ai = aiRoteiro([
    'Que legal! Qual o público e tem data prevista? 🎤[PERFIL:palestra]',
    'Perfeito! O Dr. José Simeão retorna pra você. 🌿\n[RESUMO_INICIO]\nConvite para palestra em associacao. Sem data definida.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
  ]);
  turno(st, 'oi', ai);
  turno(st, 'Palestra', ai);
  turno(st, 'quero convidar pra uma palestra', ai);
  const r = turno(st, 'sem data ainda', ai); show(r);
  check('qualificou sem prescricao', r.saida.qualificado === true);
  check('trava nao exigiu prescricao', !/prescrição médica/i.test(r.msg), r.msg);
  check('CRM perfil palestra', r.crm.perfil === 'palestra');
}

// ================================================================ T
head('CENARIO T — a trava de prescricao vale SO para paciente/familiar');
{
  // profissional tentando fechar sem prescricao: deve passar
  const st1 = novoState('5511900000018', 'P');
  const ai1 = aiRoteiro(['Certo! 🌿[PERFIL:profissional]\n[RESUMO_INICIO]\nMedico busca consultoria.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]']);
  turno(st1, 'oi', ai1); turno(st1, 'P', ai1);
  const r1 = turno(st1, 'sou medico', ai1);
  check('profissional passa sem prescricao', r1.saida.atendimentoFinalizado === true);

  // paciente tentando fechar sem prescricao: deve travar
  const st2 = novoState('5511900000019', 'C');
  const ai2 = aiRoteiro(['Certo! 🌿[PERFIL:cliente]\n[RESUMO_INICIO]\nPaciente busca HC.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]']);
  turno(st2, 'oi', ai2); turno(st2, 'C', ai2);
  const r2 = turno(st2, 'quero pra mim', ai2);
  check('paciente e travado sem prescricao', r2.saida.atendimentoFinalizado === false);
  check('paciente recebe a pergunta de corte', /prescrição médica/i.test(r2.msg), r2.msg);
}

// ================================================================ U
head('CENARIO U — aviso ao advogado vai como template (fora da janela de 24h)');
{
  const st = novoState('5511900000020', 'Teste');
  const ai = aiRoteiro([
    'Entendi! Ja tem prescricao medica? 🌿[PERFIL:cliente]',
    'Otimo! O Dr. Jose Simeao fala com voce em breve. 🌿[PRESCRICAO:sim]\n[RESUMO_INICIO]\nBusca HC autocultivo.\nPrescricao medica: sim.\nLaudo agronomico: nao informado.\n[RESUMO_FIM]\n[ATENDIMENTO_CONCLUIDO]',
  ]);
  turno(st, 'oi', ai);
  turno(st, 'Teste', ai);
  turno(st, 'quero HC pra uso proprio', ai);
  const r = turno(st, 'tenho sim', ai);

  check('gerou o aviso', !!r.aviso);
  const t = r.aviso.template;
  check('usa o template resumo_conversa', t.name === 'resumo_conversa', t.name);
  check('idioma pt_BR', t.language.code === 'pt_BR', t.language.code);
  check('type = template (nao texto livre)', r.aviso.type === 'template', r.aviso.type);

  const ps = t.components[0].parameters;
  check('4 parametros', ps.length === 4, ps.length);
  check('nomes batem com o template aprovado',
        JSON.stringify(ps.map(x => x.parameter_name)) ===
        JSON.stringify(['nome_cliente','whatsapp_cliente','servico','resumo_atendimento']),
        ps.map(x => x.parameter_name));
  check('nenhum parametro com quebra de linha',
        ps.every(x => !/[\r\n\t]/.test(x.text)), ps.map(x => x.text));
  check('nenhum parametro vazio', ps.every(x => x.text && x.text.length > 0));
  check('resumo chegou no parametro certo',
        /Busca HC autocultivo/.test(ps[3].text), ps[3].text);
}

console.log('\n' + '='.repeat(70));
console.log(falhas === 0 ? 'TODOS OS TESTES PASSARAM ✅' : `${falhas} VERIFICACAO(OES) FALHARAM ❌`);
console.log('='.repeat(70));
process.exit(falhas === 0 ? 0 : 1);
