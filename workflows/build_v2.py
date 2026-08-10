# -*- coding: utf-8 -*-
"""Gera o workflow v2 (humanizado + CRM SyncHub) sem tocar no workflow de producao."""
import json

OUT = "workflows/Agente_Juridico_Cannabis_v2_SyncHub.json"

# ---------------------------------------------------------------- CODE NODES

CODE_EXTRAIR = r"""const input = $input.all()[0].json;
const global = $getWorkflowStaticData('global');

if (input.statuses?.length || input.status) return [];
if (!input.messages?.length) return [];
if (input.field && input.field !== 'messages') return [];

const contact = input.contacts?.[0] || {};
const message = input.messages[0];
const phone = contact.wa_id || message.from || '';
const pushName = contact.profile?.name || '';
const tipoMensagem = message.type || '';
const messageId = message.id || '';
const timestamp = message.timestamp || '';

if (Math.floor(Date.now() / 1000) - parseInt(timestamp) > 30) return [];

if (!global.messagesProcessadas) global.messagesProcessadas = {};
const agoraMs = Date.now();
if (global.messagesProcessadas[messageId] && (agoraMs - global.messagesProcessadas[messageId]) < 300000) return [];
global.messagesProcessadas[messageId] = agoraMs;

for (const id in global.messagesProcessadas) {
  if (agoraMs - global.messagesProcessadas[id] > 600000) delete global.messagesProcessadas[id];
}

let textoRecebido = '';
if (tipoMensagem === 'text') textoRecebido = message.text?.body || '';
else if (tipoMensagem === 'button') textoRecebido = message.button?.text || '';
else if (tipoMensagem === 'interactive') {
  textoRecebido = message.interactive?.button_reply?.title || message.interactive?.list_reply?.title || '';
}

if (!textoRecebido || !phone) return [];

const deveResetar = ['reiniciar', 'menu', 'recomeçar', 'recomecar', 'reset'].includes(textoRecebido.toLowerCase().trim());

return [{ json: { phone, pushName, textoRecebido, tipoMensagem, messageId, timestamp, deveResetar } }];
"""

CODE_SESSAO = r"""const input = $input.all()[0].json;
const { phone, pushName, textoRecebido } = input;
const global = $getWorkflowStaticData('global');
const agora = Date.now();

if (!global.sessoes) global.sessoes = {};

if (input.deveResetar || (global.sessoes[phone] && agora - (global.sessoes[phone].ultimaAtividade || 0) > 7200000)) {
  delete global.sessoes[phone];
}

if (!global.sessoes[phone]) {
  global.sessoes[phone] = {
    etapa: 'inicio', perfil: '', nome: '', servico: '',
    email: '', telefone: '', crmId: '',
    prescricao: '', mensagensCount: 0, ultimaAtividade: agora
  };
}

const s = global.sessoes[phone];
s.mensagensCount = (s.mensagensCount || 0) + 1;
s.ultimaAtividade = agora;

return [{ json: {
  phone, pushName, textoRecebido, message: textoRecebido,
  etapa: s.etapa, perfil: s.perfil || '', nome: s.nome || '',
  servico: s.servico || '', email: s.email || '', telefone: s.telefone || '',
  crmId: s.crmId || '', prescricao: s.prescricao || '',
  mensagensCount: s.mensagensCount
} }];
"""

CODE_BOASVINDAS = r"""const { phone, pushName = 'cliente' } = $input.all()[0].json;
const global = $getWorkflowStaticData('global');
if (!global.sessoes) global.sessoes = {};
global.sessoes[phone] = {
  etapa: 'aguardando_nome', perfil: '', nome: '', servico: '',
  email: '', telefone: '', crmId: '', prescricao: '',
  mensagensCount: 1, ultimaAtividade: Date.now()
};

const mensagem = `Oi! 🌿 Sou a *Ana*, do *Escritório José Simeão Advocacia*, especializado em *Cannabis Medicinal*.\n\nPra começar, como você se chama? 😊`;

return [{ json: { phone, pushName, message: mensagem, etapa: 'aguardando_nome' } }];
"""

CODE_NOME_MENU = r"""const dados = $('Extrair Dados da Mensagem').item.json;
const global = $getWorkflowStaticData('global');
if (!global.sessoes) global.sessoes = {};
if (!global.sessoes[dados.phone]) global.sessoes[dados.phone] = {};

const bruto = (dados.textoRecebido || '').trim();
const nome = bruto.length >= 2 && bruto.length <= 60 ? bruto : (dados.pushName || 'cliente');
Object.assign(global.sessoes[dados.phone], {
  nome, etapa: 'agente_ia', perfil: '', servico: '', prescricao: '',
  resumo: '', statusLead: '', ultimaAtividade: Date.now()
});

const mensagem = `Prazer, *${nome}*! 😊

Me conta, o que te trouxe até aqui hoje?`;

return [{ json: { phone: dados.phone, pushName: dados.pushName, nome, message: mensagem, etapa: 'agente_ia' } }];
"""

CODE_CONTEXTO = r"""const input = $input.all()[0].json;
const global = $getWorkflowStaticData('global');
if (!global.sessoes) global.sessoes = {};
if (!global.sessoes[input.phone]) global.sessoes[input.phone] = {};
const s = global.sessoes[input.phone];
s.ultimaAtividade = Date.now();

const mensagemUsuario = (input.textoRecebido || input.message || '').trim();
const mensagensCount = s.mensagensCount || 0;

const emailMatch = mensagemUsuario.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/);
if (emailMatch && !s.email) s.email = emailMatch[0];

const telMatch = mensagemUsuario.replace(/\D/g, '');
if (!s.telefone && telMatch.length >= 10 && telMatch.length <= 13) s.telefone = telMatch;

const base = {
  ...input,
  nome: s.nome || '',
  perfil: s.perfil || '',
  servico: s.servico || '',
  email: s.email || '',
  telefone: s.telefone || '',
  crmId: s.crmId || '',
  prescricao: s.prescricao || '',
  mensagemUsuario,
  mensagensCount
};

const querAdvogado = ['falar com advogado','quero advogado','falar com humano','atendente','quero uma pessoa']
  .some(p => mensagemUsuario.toLowerCase().includes(p));

if (querAdvogado) {
  s.etapa = 'encerrado';
  s.statusLead = 'qualificado';
  s.resumo = s.resumo || 'Lead pediu para falar diretamente com um advogado.';
  return [{ json: { ...base,
    respostaPronta: `Claro! Já avisei o *Dr. José Simeão* e ele entra em contato com você por aqui. 🌿`,
    resumo: s.resumo, statusLead: 'qualificado', atendimentoFinalizado: true, qualificado: true } }];
}

// Corte deterministico: sem prescricao medica o HC nao avanca.
if (s.perfil === 'cliente' && s.prescricao === 'Nao') {
  s.etapa = 'encerrado';
  s.statusLead = 'nao_qualificado';
  s.resumo = 'Lead busca HC para autocultivo, mas ainda NAO possui prescricao medica. Orientado a providenciar a prescricao antes de dar entrada no processo.';
  const msg = `Entendi, *${s.nome || 'tudo bem'}*. 🌿\n\nPra entrar com o *HC de autocultivo* o primeiro passo é ter a *prescrição médica* indicando o uso de Cannabis — é ela que sustenta o pedido judicial.\n\nO caminho é procurar um *médico prescritor* (muitos atendem por telemedicina) para avaliar seu caso e emitir a prescrição. Com ela em mãos, é só voltar aqui que a gente dá sequência! 💚`;
  return [{ json: { ...base, prescricao: 'Nao',
    respostaPronta: msg, resumo: s.resumo,
    statusLead: 'nao_qualificado', atendimentoFinalizado: true, qualificado: false } }];
}

// TETO DE TURNOS: a IA tem no maximo 5 respostas. Depois disso encerra
// com o que tiver, registrando honestamente o que ficou sem resposta.
const turnosIA = (s.turnosIA || 0) + 1;
s.turnosIA = turnosIA;

if (turnosIA > 5) {
  s.etapa = 'encerrado';
  s.statusLead = 'qualificado';
  if (!s.resumo) {
    const pr = s.prescricao === 'Sim' ? 'sim'
             : s.prescricao === 'Nao' ? 'nao' : 'nao informado';
    const p = ['Conversa encerrada automaticamente: lead respondeu de forma vaga em varias trocas.'];
    p.push('Interesse: ' + (s.servico || 'nao informado') + '.');
    if (s.perfil === 'cliente' || !s.perfil) {
      p.push('Prescricao medica: ' + pr + '.');
      p.push('Laudo agronomico: nao informado.');
      p.push('Curso de autocultivo: nao informado.');
    }
    p.push('Retomar o contato para levantar os detalhes.');
    s.resumo = p.join(' ');
  }
  return [{ json: { ...base,
    respostaPronta: `Obrigada, *${s.nome || ''}*! ✅ Já passei tudo pro *Dr. José Simeão* e ele fala com você por aqui em breve. 🌿`,
    resumo: s.resumo, statusLead: 'qualificado', atendimentoFinalizado: true, qualificado: true } }];
}

// Valvula de seguranca: conversa muito longa vai para o advogado mesmo assim.
if (mensagensCount >= 10) {
  s.etapa = 'encerrado';
  s.statusLead = 'qualificado';
  s.resumo = s.resumo || 'Conversa longa encerrada automaticamente. Verificar historico com o lead.';
  return [{ json: { ...base,
    respostaPronta: `Obrigada pelas informações! ✅ Já encaminhei pro *Dr. José Simeão* e ele fala com você em breve. 🌿`,
    resumo: s.resumo, statusLead: 'qualificado', atendimentoFinalizado: true, qualificado: true } }];
}

return [{ json: { ...base, atendimentoFinalizado: false, qualificado: false } }];
"""

CODE_PROCESSAR_IA = r"""const global = $getWorkflowStaticData('global');
const ctx = $('Preparar Contexto para IA').item.json;
const s = global.sessoes?.[ctx.phone] || {};

// Caminhos deterministicos (corte de prescricao, pedido de advogado, valvula)
if (ctx.respostaPronta) {
  return [{ json: {
    ...ctx,
    message: ctx.respostaPronta,
    resumo: ctx.resumo || '',
    statusLead: ctx.statusLead || '',
    atendimentoFinalizado: true,
    qualificado: !!ctx.qualificado
  } }];
}

const agente = $('AI Agent').item.json;
let resposta = agente?.output || agente?.text || agente?.content || agente?.response
  || 'Desculpa, tive um probleminha técnico aqui. Pode repetir? 🌿';

const semPrescricao = /\[SEM_PRESCRICAO\]/i.test(resposta);
const concluido = /\[ATENDIMENTO_CONCLUIDO\]/i.test(resposta);

// A IA identifica o assunto pela conversa, sem menu numerado.
const SERVICOS = {
  cliente: 'HC para Autocultivo Medicinal',
  palestra: 'Palestra sobre Cannabis Medicinal',
  profissional: 'Consultoria para Profissional de Saude',
  outro: 'Outro assunto'
};
const mPerfil = resposta.match(/\[PERFIL:\s*(cliente|palestra|profissional|outro)\s*\]/i);
if (mPerfil && global.sessoes?.[ctx.phone]) {
  const perfil = mPerfil[1].toLowerCase();
  global.sessoes[ctx.phone].perfil = perfil;
  global.sessoes[ctx.phone].servico = SERVICOS[perfil];
}

const mPresc = resposta.match(/\[PRESCRICAO:\s*(sim|nao|não)\s*\]/i);
if (mPresc && global.sessoes?.[ctx.phone]) {
  global.sessoes[ctx.phone].prescricao = /sim/i.test(mPresc[1]) ? 'Sim' : 'Nao';
}

const resumoMatch = resposta.match(/\[RESUMO_INICIO\]([\s\S]*?)\[RESUMO_FIM\]/i);
const resumo = resumoMatch ? resumoMatch[1].trim() : (s.resumo || '');

// Guarda: a saudacao inicial vem de um Code node e nao entra na memoria da IA,
// entao ela as vezes cumprimenta e se apresenta de novo. Remove os dois.
function semReapresentacao(t) {
  let x = t;
  x = x.replace(/^\s*(ol[aá]|oi|bom dia|boa tarde|boa noite)\b[^\n]{0,50}?[!.,]\s*/i, '');
  x = x.replace(/^\s*(ol[aá]|oi|bom dia|boa tarde|boa noite)\b[\s,!]*/i, '');
  x = x.replace(/\b(aqui [eé] a ana|sou a ana|quem fala [eé] a ana)\b[^.!?\n]*[.!?]?\s*/gi, '');
  return x.trim();
}
const respLimpa = semReapresentacao(resposta);
if (respLimpa.length > 10) resposta = respLimpa;

resposta = resposta
  .replace(/\[RESUMO_INICIO\][\s\S]*?\[RESUMO_FIM\]/gi, '')
  .replace(/\s*\[ATENDIMENTO_CONCLUIDO\]\s*/gi, '')
  .replace(/\s*\[SEM_PRESCRICAO\]\s*/gi, '')
  .replace(/\s*\[PERFIL:[^\]]*\]\s*/gi, '')
  .replace(/\s*\[PRESCRICAO:[^\]]*\]\s*/gi, '')
  .trim();

// TRAVA ANTI-ALUCINACAO: bloqueia encerramento precoce, mesmo que a IA peca.
// Sem perfil definido ou sem resposta sobre prescricao, o atendimento NAO fecha.
if (concluido) {
  const sNow = global.sessoes?.[ctx.phone] || {};
  if (!sNow.perfil) {
    return [{ json: { ...ctx,
      message: 'Só pra eu te direcionar certinho: isso é pra você mesmo, pra alguém da família, ou você é profissional de saúde? 🌿',
      resumo: '', statusLead: '', atendimentoFinalizado: false, qualificado: false } }];
  }
  if (sNow.perfil === 'cliente' && !sNow.prescricao) {
    return [{ json: { ...ctx,
      message: 'Antes de encaminhar pro Dr. José Simeão, me confirma uma coisa importante: você já tem a *prescrição médica* indicando o uso de Cannabis? 🌿',
      resumo: '', statusLead: '', atendimentoFinalizado: false, qualificado: false } }];
  }
}

let statusLead = '';
let atendimentoFinalizado = false;
let qualificado = false;

if (semPrescricao) {
  statusLead = 'nao_qualificado';
  atendimentoFinalizado = true;
  if (global.sessoes?.[ctx.phone]) {
    global.sessoes[ctx.phone].etapa = 'encerrado';
    global.sessoes[ctx.phone].prescricao = 'Nao';
    global.sessoes[ctx.phone].statusLead = statusLead;
    global.sessoes[ctx.phone].resumo = resumo;
  }
} else if (concluido) {
  statusLead = 'qualificado';
  atendimentoFinalizado = true;
  qualificado = true;
  if (global.sessoes?.[ctx.phone]) {
    global.sessoes[ctx.phone].etapa = 'encerrado';
    global.sessoes[ctx.phone].statusLead = statusLead;
    global.sessoes[ctx.phone].resumo = resumo;
  }
}

const sAtual = global.sessoes?.[ctx.phone] || {};

return [{ json: {
  ...ctx,
  perfil: sAtual.perfil || ctx.perfil || '',
  servico: sAtual.servico || ctx.servico || '',
  prescricao: sAtual.prescricao || ctx.prescricao || '',
  message: resposta,
  resumo,
  statusLead,
  atendimentoFinalizado,
  qualificado
} }];
"""

CODE_POS_ATENDIMENTO = r"""const input = $input.all()[0].json;
const global = $getWorkflowStaticData('global');
const s = global.sessoes?.[input.phone] || {};
const nome = s.nome || input.pushName || '';
const trecho = nome ? `, *${nome}*` : '';

const msg = s.statusLead === 'nao_qualificado'
  ? `Fico à disposição${trecho}! 🌿 Assim que você tiver a *prescrição médica* em mãos, é só me chamar aqui que a gente dá sequência.\n\nSe quiser recomeçar o atendimento, digite *MENU*.`
  : `Seu atendimento já está com o *Dr. José Simeão*${trecho}! 🌿 Ele vai falar com você por aqui em breve.\n\nSe precisar recomeçar, digite *MENU*.`;

return [{ json: { ...input, message: msg, atendimentoFinalizado: false, qualificado: false } }];
"""

CODE_PAYLOAD_CRM = r"""const d = $input.all()[0].json;
const global = $getWorkflowStaticData('global');
const s = global.sessoes?.[d.phone] || {};

const payload = {
  nome: d.nome || s.nome || '',
  telefone: d.phone || '',
  telefoneContato: d.telefone || s.telefone || d.phone || '',
  email: d.email || s.email || '',
  origem: 'WhatsApp - Ana (Simeao Advogados)',
  perfil: d.perfil || s.perfil || '',
  servico: d.servico || s.servico || '',
  statusLead: d.statusLead || s.statusLead || '',
  qualificado: !!d.qualificado,
  prescricaoMedica: d.prescricao || s.prescricao || '',
  resumoConversa: d.resumo || s.resumo || '',
  dataAtendimento: new Date().toISOString()
};

return [{ json: { ...d, crmPayload: payload } }];
"""

# ---------------------------------------------------------------- PROMPT

PROMPT = """Você é a *Ana*, do Escritório José Simeão Advocacia, especializado em Cannabis Medicinal. Você atende pelo WhatsApp.

Você não é uma entrevistadora — você é uma triagem rápida e acolhedora. Seu trabalho é entender o essencial em pouquíssimas mensagens e encaminhar a pessoa ao advogado. Conversa arrastada faz o lead desistir.

CONTEXTO (uso interno — nunca mostre ao lead):
Nome: {{ $('Preparar Contexto para IA').item.json.nome }}
Assunto identificado: {{ $('Preparar Contexto para IA').item.json.perfil }}
Prescrição médica: {{ $('Preparar Contexto para IA').item.json.prescricao }}
WhatsApp: {{ $('Preparar Contexto para IA').item.json.phone }}
Mensagem atual: {{ $('Preparar Contexto para IA').item.json.mensagemUsuario }}

════════════════════════════════
REGRA DE OURO — O FUNIL
════════════════════════════════
Você tem no máximo *3 mensagens* para conduzir do início ao encaminhamento:

  1ª — ACOLHE em uma linha + faz a PERGUNTA DE CORTE
  2ª — faz UMA ÚNICA pergunta de aprofundamento (que junta tudo que falta)
  3ª — FECHA: agradece, diz o próximo passo e encerra

Se a pessoa já entregou a informação antes de você perguntar, PULE a etapa e vá direto para a próxima. Fechar em 2 mensagens é melhor que em 3.

Esse teto vale MESMO se a pessoa responder de forma vaga. Você tem no máximo 5 mensagens no total, contando as tentativas de esclarecimento. Ao chegar perto disso, feche com o que tiver — nunca fique perguntando indefinidamente.

NUNCA faça uma pergunta de cada vez em sequência. NUNCA peça um dado que já foi dito. NUNCA prolongue a conversa para "confirmar" algo que já está claro. Ao menor sinal de que você tem o suficiente, feche.

════════════════════════════════
O QUE JÁ ACONTECEU (nunca repita)
════════════════════════════════
Esta conversa NÃO está começando agora. Antes de você entrar, já aconteceu:
  1. A pessoa foi cumprimentada e você já se apresentou como Ana, do escritório.
  2. Você já perguntou o nome dela e ela já respondeu.
  3. Você já perguntou o que a trouxe até aqui.

Sua mensagem é a CONTINUAÇÃO dessa conversa. Portanto:
- NUNCA comece com saudação ("Olá", "Oi", "Bom dia", "Seja bem-vindo").
- NUNCA se apresente de novo ("Aqui é a Ana", "Sou a Ana", "do Escritório José Simeão").
- NUNCA pergunte o nome — você já sabe, está no contexto acima.
- Comece direto reagindo ao que a pessoa acabou de dizer.

Quem entra em contato depois é o *Dr. José Simeão*. Chame-o sempre assim — nunca de "especialista", "nossa equipe" ou "Simeão Advogados".

════════════════════════════════
REGRA INEGOCIÁVEL — NUNCA INVENTE
════════════════════════════════
Você só pode registrar aquilo que a pessoa disse COM AS PRÓPRIAS PALAVRAS nesta conversa.

- Nunca deduza, nunca complete o raciocínio dela, nunca "assuma que sim".
- Se um assunto não foi perguntado ou não foi respondido, escreva "não informado" no resumo.
- Um resumo curto e verdadeiro vale mais que um completo e inventado. O advogado vai ligar para essa pessoa com base no que VOCÊ escrever — informação errada faz o escritório perder o cliente.

Antes de fechar, confira cada linha do resumo: existe uma frase da pessoa que sustenta isso? Se não existe, apague a linha.

════════════════════════════════
QUANDO A RESPOSTA NÃO FOR CLARA
════════════════════════════════
Se a pessoa responder algo truncado, cortado, ambíguo ou que não responde ao que você perguntou (ex: "para so", "sim", "ok", "?"), NÃO adivinhe e NÃO siga em frente.

Peça esclarecimento de forma leve e específica:
  "Desculpa, acho que sua mensagem cortou! Você quis dizer que é pra uso próprio?"
  "Só pra eu entender direito: você já tem a prescrição em mãos ou ainda vai procurar o médico?"

Nunca defina o perfil nem marque uma informação como confirmada com base em resposta incompleta. Pedir para repetir é melhor que registrar errado.

LIMITE: você tem no máximo *2 tentativas* de esclarecimento na conversa inteira. Se depois disso a pessoa continuar vaga ou monossilábica, PARE de perguntar. Agradeça, encaminhe ao Dr. José Simeão e escreva "não informado" no resumo para tudo que ficou em aberto. Insistir cansa e faz o lead sumir.

Ao pedir esclarecimento, faça UMA pergunta aberta. Evite enumerar as três possibilidades como se fosse um menu.

════════════════════════════════
COMO VOCÊ FALA
════════════════════════════════
- Máximo 3 linhas por mensagem. Máximo 1 emoji 🌿
- NUNCA ofereça listas de opções numeradas ("1 - ... 2 - ..."). Entrega que você é um bot.
- Reaja em UMA linha ao que a pessoa disse, e emende a pergunta na mesma mensagem.
- Não repita a saudação nem pergunte o nome de novo.
- Nunca dê orientação jurídica, não prometa resultado, não fale de valores.
- Se perguntarem se você é humana ou IA, responda com honestidade em uma linha e siga.

════════════════════════════════
O QUE QUALIFICA CADA LEAD (regra do escritório)
════════════════════════════════
São três caminhos, e cada um tem uma regra própria de qualificação:

▸ PACIENTE OU FAMILIAR (uso próprio ou de alguém da família)
  QUALIFICA SOMENTE COM *PRESCRIÇÃO MÉDICA*. É condição obrigatória — sem ela o
  pedido de HC não tem base e o caso não avança. Se não tiver, oriente a
  providenciar e encerre. Essa é a única regra de corte de todo o atendimento.

▸ PROFISSIONAL DE SAÚDE (qualquer área)
  QUALIFICA SEMPRE. O assunto aqui é *consultoria* para a atuação dele, não
  tratamento pessoal. NUNCA pergunte sobre prescrição médica, laudo agronômico
  ou curso de autocultivo — nada disso se aplica a ele.

▸ PALESTRA
  QUALIFICA SEMPRE. É simplesmente um convite/contratação de palestra. Sem
  requisito nenhum. Não confunda com os outros dois caminhos.

ATENÇÃO: se um profissional de saúde procurar o escritório para uso PESSOAL dele
(como paciente, não como profissional), aí ele é PACIENTE — e vale a regra da
prescrição médica. O que define o caminho é a intenção, não a profissão.

════════════════════════════════
PRIMEIRO: IDENTIFIQUE O ASSUNTO SEM PERGUNTAR EM MENU
════════════════════════════════
Pela fala da pessoa, descubra em qual caso ela se encaixa:

  cliente      → paciente ou familiar que precisa de ajuda jurídica (HC para autocultivo)
  palestra     → quer contratar/convidar para uma palestra
  profissional → QUALQUER profissional de saúde buscando consultoria — médico, dentista,
                 fisioterapeuta, veterinário, farmacêutico, psicólogo, nutricionista,
                 enfermeiro, terapeuta ocupacional, biomédico e afins. Não importa o nicho:
                 se a pessoa atua na saúde e busca orientação profissional, é este caminho.

Quase sempre a primeira frase já revela ("minha filha tem epilepsia", "sou veterinária", "queria uma palestra"). Marque com [PERFIL:cliente] (ou palestra / profissional) e siga direto — sem confirmar o óbvio.

Só se estiver realmente ambíguo, faça UMA pergunta curta e humana. Nunca ofereça a lista de opções. Se não for nenhum dos três, marque [PERFIL:outro] e encaminhe.

════════════════════════════════
FUNIL "cliente" — HC para autocultivo
════════════════════════════════
Pré-requisito inegociável: *prescrição médica*. Sem ela o caso não avança.

1ª MENSAGEM — acolha em uma linha e já pergunte pela prescrição, encaixado no que a pessoa contou.
  Ex: "Poxa, imagino o quanto isso pesa. E o médico dela já chegou a prescrever a Cannabis? 🌿"
  Marque [PRESCRICAO:sim] ou [PRESCRICAO:nao] assim que souber.

  ▸ SEM PRESCRIÇÃO → encerre AQUI. Acolha, explique em uma linha que a prescrição é a base do pedido, oriente a procurar um médico prescritor (muitos atendem por telemedicina), convide a voltar. Feche com o bloco de resumo + [SEM_PRESCRICAO].

2ª MENSAGEM (só se TEM prescrição) — comemore em meia linha e faça UMA pergunta que junta tudo que falta, de forma fluida:
  Ex: "Ótimo, isso já resolve o principal! Me conta rapidinho: você já tem o laudo agronômico do cultivo e chegou a fazer algum curso de autocultivo?"
  Se ela não souber o que é laudo agronômico, explique em uma linha na mensagem seguinte e já feche.

3ª MENSAGEM — feche. Agradeça e diga que o *Dr. José Simeão* entra em contato. Bloco de resumo + [ATENDIMENTO_CONCLUIDO].

OBRIGATÓRIO: você NÃO pode encerrar um atendimento de perfil "cliente" sem ter perguntado sobre a prescrição médica e recebido uma resposta clara. Se ainda não perguntou, essa é sua próxima mensagem — nunca o encerramento.

════════════════════════════════
FUNIL "palestra"
════════════════════════════════
Qualifica sempre — palestra é palestra, não tem requisito nenhum.

1ª — reaja e pergunte de uma vez o público/instituição e a previsão de data.
2ª — peça o melhor contato (e-mail ou telefone) e JÁ FECHE na mesma mensagem se possível.
Encerre com resumo + [ATENDIMENTO_CONCLUIDO].

════════════════════════════════
FUNIL "profissional"
════════════════════════════════
Vale para qualquer área da saúde. Qualifica sempre — não existe pergunta de corte aqui.

1ª — reaja e pergunte de uma vez a área de atuação e o que exatamente ela busca
     (orientação para prescrever, consultoria para a clínica, dúvida regulatória).
2ª — feche e encaminhe ao Dr. José Simeão.

NUNCA pergunte sobre prescrição médica, laudo agronômico ou curso de autocultivo —
esses assuntos são de paciente e não fazem sentido para quem busca consultoria.
Encerre com resumo + [ATENDIMENTO_CONCLUIDO].

════════════════════════════════
COMO ENCERRAR (formato obrigatório)
════════════════════════════════
Despedida curta para o lead + o bloco abaixo:

[RESUMO_INICIO]
Resumo objetivo em até 5 linhas, escrito para o ADVOGADO ler. Registre APENAS o que a pessoa disse nesta conversa: o que ela procura, contexto de saúde, prescrição médica, laudo agronômico, curso de autocultivo e detalhes relevantes.

Para cada item que não foi perguntado ou não foi respondido, escreva exatamente "não informado". NUNCA escreva que a pessoa possui algo sem que ela tenha dito isso. Sem emojis, direto ao ponto.

Exemplo de resumo correto quando pouca coisa foi dita:
Busca HC para autocultivo, uso próprio. Prescrição médica: não informado. Laudo agronômico: não informado. Curso de autocultivo: não informado.
[RESUMO_FIM]
[ATENDIMENTO_CONCLUIDO]

Se o encerramento for por FALTA DE PRESCRIÇÃO MÉDICA, troque [ATENDIMENTO_CONCLUIDO] por [SEM_PRESCRICAO].

REGRA DAS TAGS: [PERFIL:...] e [PRESCRICAO:...] podem aparecer em qualquer resposta, assim que a informação ficar clara. [ATENDIMENTO_CONCLUIDO] e [SEM_PRESCRICAO] só no encerramento. Todas são removidas antes de chegar ao lead."""

# ---------------------------------------------------------------- NODES

def code_node(name, code, node_id, pos):
    return {
        "parameters": {"jsCode": code},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": pos,
        "id": node_id,
        "name": name,
    }

nodes = []

nodes.append({
    "parameters": {"updates": ["messages"], "options": {}},
    "type": "n8n-nodes-base.whatsAppTrigger",
    "typeVersion": 1,
    "position": [-2200, 0],
    "id": "v2-trigger-0001",
    "name": "WhatsApp Trigger",
    "webhookId": "b2f1c9d0-1111-4a2b-9c3d-000000000001",
    "credentials": {"whatsAppTriggerApi": {"id": "bJFFW3HPG0uqmxel", "name": "WhatsApp OAuth account"}},
})

nodes.append(code_node("Extrair Dados da Mensagem", CODE_EXTRAIR, "v2-extrair-0002", [-1980, 0]))
nodes.append(code_node("Buscar Sessao do Usuario", CODE_SESSAO, "v2-sessao-0003", [-1760, 0]))

nodes.append({
    "parameters": {
        "rules": {"values": [
            {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3},
                            "conditions": [{"id": "r1", "leftValue": "={{ $json.etapa }}", "rightValue": "inicio",
                                            "operator": {"type": "string", "operation": "equals"}}],
                            "combinator": "and"},
             "renameOutput": True, "outputKey": "inicio"},
            {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3},
                            "conditions": [{"id": "r2", "leftValue": "={{ $json.etapa }}", "rightValue": "aguardando_nome",
                                            "operator": {"type": "string", "operation": "equals"}}],
                            "combinator": "and"},
             "renameOutput": True, "outputKey": "aguardando_nome"},
            {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3},
                            "conditions": [{"id": "r4", "leftValue": "={{ $json.etapa }}", "rightValue": "agente_ia",
                                            "operator": {"type": "string", "operation": "equals"}}],
                            "combinator": "and"},
             "renameOutput": True, "outputKey": "agente_ia"},
            {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3},
                            "conditions": [{"id": "r5", "leftValue": "={{ $json.etapa }}", "rightValue": "encerrado",
                                            "operator": {"type": "string", "operation": "equals"}}],
                            "combinator": "and"},
             "renameOutput": True, "outputKey": "encerrado"},
        ]},
        "options": {"fallbackOutput": "extra"},
    },
    "type": "n8n-nodes-base.switch",
    "typeVersion": 3.2,
    "position": [-1540, 0],
    "id": "v2-switch-0004",
    "name": "Verificar Etapa da Conversa",
})

nodes.append(code_node("Montar Boas-vindas", CODE_BOASVINDAS, "v2-boasvindas-0005", [-1300, -320]))
nodes.append(code_node("Salvar Nome e Abrir Conversa", CODE_NOME_MENU, "v2-nomemenu-0006", [-1300, -140]))
nodes.append(code_node("Preparar Contexto para IA", CODE_CONTEXTO, "v2-contexto-0008", [-1300, 240]))
nodes.append(code_node("Mensagem Pos Atendimento", CODE_POS_ATENDIMENTO, "v2-pos-0019", [-1300, 460]))

nodes.append({
    "parameters": {
        "promptType": "define",
        "text": "={{ $('Preparar Contexto para IA').item.json.mensagemUsuario }}",
        "options": {"systemMessage": "=" + PROMPT},
    },
    "type": "@n8n/n8n-nodes-langchain.agent",
    "typeVersion": 3,
    "position": [-1060, 240],
    "id": "v2-agent-0009",
    "name": "AI Agent",
})

nodes.append({
    "parameters": {
        "model": {"__rl": True, "value": "claude-sonnet-4-6", "mode": "list", "cachedResultName": "Claude Sonnet 4.6"},
        "options": {},
    },
    "type": "@n8n/n8n-nodes-langchain.lmChatAnthropic",
    "typeVersion": 1.5,
    "position": [-1120, 440],
    "id": "v2-anthropic-0010",
    "name": "Anthropic Chat Model",
    "credentials": {"anthropicApi": {"id": "FT3UMqdJad4KmW3P", "name": "Vitao"}},
})

nodes.append({
    "parameters": {
        "sessionIdType": "customKey",
        "sessionKey": "={{ $('Extrair Dados da Mensagem').item.json.phone }}",
        "contextWindowLength": 12,
    },
    "type": "@n8n/n8n-nodes-langchain.memoryPostgresChat",
    "typeVersion": 1.3,
    "position": [-960, 440],
    "id": "v2-memory-0011",
    "name": "Postgres Chat Memory",
    "credentials": {"postgres": {"id": "RryHpUamo58VME6T", "name": "Postgres account"}},
})

nodes.append(code_node("Processar Resposta da IA", CODE_PROCESSAR_IA, "v2-procia-0012", [-820, 240]))

nodes.append({
    "parameters": {
        "operation": "send",
        "phoneNumberId": "1120643227802579",
        "recipientPhoneNumber": "={{ $json.phone }}",
        "textBody": "={{ $json.message }}",
        "additionalFields": {},
    },
    "type": "n8n-nodes-base.whatsApp",
    "typeVersion": 1.1,
    "position": [-600, 240],
    "id": "v2-envcliente-0013",
    "name": "Enviar mensagem cliente",
    "webhookId": "b2f1c9d0-1111-4a2b-9c3d-000000000013",
    "credentials": {"whatsAppApi": {"id": "iwP7SMgYbk6Pzkhs", "name": "Simeao"}},
})

nodes.append({
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "fim1",
                "leftValue": "={{ $json.atendimentoFinalizado }}",
                "rightValue": "true",
                "operator": {"type": "boolean", "operation": "true", "singleValue": True},
            }],
            "combinator": "and",
        },
        "looseTypeValidation": True,
        "options": {},
    },
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [-600, 460],
    "id": "v2-iffim-0014",
    "name": "Atendimento Finalizado?",
})

nodes.append(code_node("Montar Payload CRM", CODE_PAYLOAD_CRM, "v2-payload-0015", [-160, 140]))

nodes.append({
    "parameters": {
        "method": "POST",
        "url": "https://SUBSTITUA-PELA-URL-DA-API-SYNCHUB/leads",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify($json.crmPayload) }}",
        "options": {},
    },
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [-160, 380],
    "id": "v2-crm-0016",
    "name": "Enviar Lead para o CRM",
    "onError": "continueRegularOutput",
    "notes": "SyncHub CRM - preencher URL e selecionar a credencial SyncHub apos importar.",
})

nodes.append({
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "qual1",
                "leftValue": "={{ $json.qualificado }}",
                "rightValue": "true",
                "operator": {"type": "boolean", "operation": "true", "singleValue": True},
            }],
            "combinator": "and",
        },
        "looseTypeValidation": True,
        "options": {},
    },
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [-160, 560],
    "id": "v2-ifqual-0017",
    "name": "Lead Qualificado?",
})

NOTIF = (
    "=🌿 *Novo Lead - Simeao Advogados*\n\n"
    "Atendimento WhatsApp\n\n"
    "Nome: {{ $json.nome || 'Nao informado' }}\n"
    "WhatsApp: {{ $json.phone || 'Nao informado' }}\n"
    "Servico: {{ $json.servico || 'Nao informado' }}\n\n"
    "📋 *Resumo da conversa:*\n{{ $json.resumo || 'Sem resumo registrado' }}\n\n"
    "⚠️ *Entrar em contato o quanto antes!*"
)

nodes.append({
    "parameters": {
        "operation": "send",
        "phoneNumberId": "1120643227802579",
        "recipientPhoneNumber": "+55 11 94132-1970",
        "textBody": NOTIF,
        "additionalFields": {},
    },
    "type": "n8n-nodes-base.whatsApp",
    "typeVersion": 1.1,
    "position": [80, 560],
    "id": "v2-notif-0018",
    "name": "Notificar Advogado",
    "webhookId": "b2f1c9d0-1111-4a2b-9c3d-000000000018",
    "credentials": {"whatsAppApi": {"id": "iwP7SMgYbk6Pzkhs", "name": "Simeao"}},
})

# ---------------------------------------------------------------- CONNECTIONS

connections = {
    "WhatsApp Trigger": {"main": [[{"node": "Extrair Dados da Mensagem", "type": "main", "index": 0}]]},
    "Extrair Dados da Mensagem": {"main": [[{"node": "Buscar Sessao do Usuario", "type": "main", "index": 0}]]},
    "Buscar Sessao do Usuario": {"main": [[{"node": "Verificar Etapa da Conversa", "type": "main", "index": 0}]]},
    "Verificar Etapa da Conversa": {"main": [
        [{"node": "Montar Boas-vindas", "type": "main", "index": 0}],
        [{"node": "Salvar Nome e Abrir Conversa", "type": "main", "index": 0}],
        [{"node": "Preparar Contexto para IA", "type": "main", "index": 0}],
        [{"node": "Mensagem Pos Atendimento", "type": "main", "index": 0}],
        [{"node": "Montar Boas-vindas", "type": "main", "index": 0}],
    ]},
    "Mensagem Pos Atendimento": {"main": [[{"node": "Enviar mensagem cliente", "type": "main", "index": 0}]]},
    "Montar Boas-vindas": {"main": [[{"node": "Enviar mensagem cliente", "type": "main", "index": 0}]]},
    "Salvar Nome e Abrir Conversa": {"main": [[{"node": "Enviar mensagem cliente", "type": "main", "index": 0}]]},
    "Preparar Contexto para IA": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
    "AI Agent": {"main": [[{"node": "Processar Resposta da IA", "type": "main", "index": 0}]]},
    "Anthropic Chat Model": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
    "Postgres Chat Memory": {"ai_memory": [[{"node": "AI Agent", "type": "ai_memory", "index": 0}]]},
    "Processar Resposta da IA": {"main": [[
        {"node": "Enviar mensagem cliente", "type": "main", "index": 0},
        {"node": "Atendimento Finalizado?", "type": "main", "index": 0},
    ]]},
    "Enviar mensagem cliente": {"main": [[]]},
    "Atendimento Finalizado?": {"main": [
        [{"node": "Montar Payload CRM", "type": "main", "index": 0}],
        [],
    ]},
    "Montar Payload CRM": {"main": [[
        {"node": "Enviar Lead para o CRM", "type": "main", "index": 0},
        {"node": "Lead Qualificado?", "type": "main", "index": 0},
    ]]},
    "Enviar Lead para o CRM": {"main": [[]]},
    "Lead Qualificado?": {"main": [
        [{"node": "Notificar Advogado", "type": "main", "index": 0}],
        [],
    ]},
}

workflow = {
    "name": "Agente Juridico Cannabis - v2 Humanizado (SyncHub)",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1"},
    "pinData": {},
    "meta": {"instanceId": "v2-synchub-humanizado"},
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(workflow, f, ensure_ascii=False, indent=2)

print("OK ->", OUT)
print("nodes:", len(nodes))
