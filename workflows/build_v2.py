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
Object.assign(global.sessoes[dados.phone], { nome, etapa: 'menu', ultimaAtividade: Date.now() });

const mensagem = `Prazer, *${nome}*! 😊\n\nMe conta como posso te ajudar:\n\n1️⃣ - Sou *paciente ou familiar* e preciso de ajuda jurídica (*HC para autocultivo*)\n2️⃣ - Tenho interesse em *palestra* sobre Cannabis Medicinal\n3️⃣ - Sou *médico, dentista, fisioterapeuta ou veterinário* e desejo uma consultoria\n\nÉ só digitar o número 👇`;

return [{ json: { phone: dados.phone, pushName: dados.pushName, nome, message: mensagem, etapa: 'menu' } }];
"""

CODE_MENU = r"""const input = $input.all()[0].json;
const global = $getWorkflowStaticData('global');
if (!global.sessoes) global.sessoes = {};
if (!global.sessoes[input.phone]) global.sessoes[input.phone] = {};
const s = global.sessoes[input.phone];
s.ultimaAtividade = Date.now();

const opcao = (input.textoRecebido || '').trim()
  .replace(/1️⃣/g, '1').replace(/2️⃣/g, '2').replace(/3️⃣/g, '3');

const nome = s.nome || 'tudo bem';

const opcoes = {
  '1': {
    perfil: 'cliente',
    servico: 'HC para Autocultivo Medicinal',
    mensagem: `Entendi, *${nome}*. 🌿 Vamos ver como o escritório pode te ajudar com o *HC para autocultivo*.\n\nUma coisa importante logo de início: você já tem *prescrição médica* indicando o uso de Cannabis?`
  },
  '2': {
    perfil: 'palestra',
    servico: 'Palestra sobre Cannabis Medicinal',
    mensagem: `Que legal, *${nome}*! 🎤 O escritório realiza palestras e treinamentos sobre Cannabis Medicinal e os aspectos jurídicos do tema.\n\nMe conta um pouco: é pra qual tipo de público ou instituição?`
  },
  '3': {
    perfil: 'profissional',
    servico: 'Consultoria para Profissional de Saúde',
    mensagem: `Ótimo, *${nome}*! 🌿 O escritório oferece consultoria para profissionais de saúde que atuam ou querem atuar com Cannabis Medicinal.\n\nMe conta sobre a sua área de atuação e o que você está buscando 👇`
  }
};

if (opcoes[opcao]) {
  const { perfil, servico, mensagem } = opcoes[opcao];
  Object.assign(s, {
    perfil, servico, etapa: 'agente_ia',
    prescricao: '', resumo: '', statusLead: '',
    perguntouPrescricao: perfil === 'cliente'
  });
  return [{ json: { ...input, perfil, servico, message: mensagem, etapa: 'agente_ia' } }];
}

return [{ json: { ...input, message: `Só pra eu te direcionar certinho, digita o *número* da opção:\n\n1️⃣ - Sou *paciente ou familiar* e preciso de ajuda jurídica (*HC para autocultivo*)\n2️⃣ - Tenho interesse em *palestra* sobre Cannabis Medicinal\n3️⃣ - Sou *médico, dentista, fisioterapeuta ou veterinário* e desejo uma consultoria` } }];
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

// Classificador de alta confianca para a pergunta de prescricao medica.
// Se ficar ambiguo, devolve '' e a IA continua investigando na conversa.
function classificaPrescricao(txt) {
  const t = txt.toLowerCase().trim();
  if (/^(1|sim|s|tenho|ja tenho|já tenho|possuo|tenho sim|sim tenho)$/.test(t)) return 'Sim';
  if (/^sim\b/.test(t) && !/\b(nao|não)\b/.test(t)) return 'Sim';
  if (/^(nao|não)\b/.test(t)) return 'Nao';
  if (/^(2|nao|não|n|nao tenho|não tenho|ainda nao|ainda não|nao possuo|não possuo)$/.test(t)) return 'Nao';
  if (/\b(tenho|possuo|consegui|tenho a receita|com receita|receituario|receituário)\b/.test(t)
      && !/\b(nao|não|ainda nao|ainda não|sem)\b/.test(t)) return 'Sim';
  if (/\b(nao tenho|não tenho|ainda nao|ainda não|sem prescricao|sem prescrição|sem receita|nao possuo|não possuo)\b/.test(t)) return 'Nao';
  return '';
}

if (s.perfil === 'cliente' && s.perguntouPrescricao && !s.prescricao) {
  const c = classificaPrescricao(mensagemUsuario);
  if (c) s.prescricao = c;
}

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
    respostaPronta: `Claro! Já vou avisar nossa equipe e um advogado entra em contato com você por aqui. 🌿`,
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

// Valvula de seguranca: conversa muito longa vai para o advogado mesmo assim.
if (mensagensCount >= 14) {
  s.etapa = 'encerrado';
  s.statusLead = 'qualificado';
  s.resumo = s.resumo || 'Conversa longa encerrada automaticamente. Verificar historico com o lead.';
  return [{ json: { ...base,
    respostaPronta: `Obrigada pelas informações! ✅ Vou encaminhar tudo pra nossa equipe e um especialista fala com você em breve. 🌿`,
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

const resumoMatch = resposta.match(/\[RESUMO_INICIO\]([\s\S]*?)\[RESUMO_FIM\]/i);
const resumo = resumoMatch ? resumoMatch[1].trim() : (s.resumo || '');

resposta = resposta
  .replace(/\[RESUMO_INICIO\][\s\S]*?\[RESUMO_FIM\]/gi, '')
  .replace(/\s*\[ATENDIMENTO_CONCLUIDO\]\s*/gi, '')
  .replace(/\s*\[SEM_PRESCRICAO\]\s*/gi, '')
  .trim();

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

return [{ json: {
  ...ctx,
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
  : `Seu atendimento já está com a nossa equipe${trecho}! 🌿 Um especialista vai falar com você por aqui em breve.\n\nSe precisar recomeçar, digite *MENU*.`;

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

PROMPT = """Você é a *Ana*, assistente do Escritório José Simeão Advocacia, especializado em Cannabis Medicinal.

Sua função é conversar de forma NATURAL e HUMANA com quem chega pelo WhatsApp, entender o caso da pessoa e passar um resumo bem feito para o advogado. Você não é um formulário — você é uma pessoa atenciosa que escuta.

DADOS DO ATENDIMENTO (use, mas nunca liste isso para o lead):
Nome: {{ $('Preparar Contexto para IA').item.json.nome }}
Perfil: {{ $('Preparar Contexto para IA').item.json.perfil }}
Serviço: {{ $('Preparar Contexto para IA').item.json.servico }}
WhatsApp: {{ $('Preparar Contexto para IA').item.json.phone }}
Prescrição médica confirmada: {{ $('Preparar Contexto para IA').item.json.prescricao }}
Mensagem atual: {{ $('Preparar Contexto para IA').item.json.mensagemUsuario }}

════════════════════════════════
COMO VOCÊ FALA
════════════════════════════════
- Tom caloroso, próximo, brasileiro. Como uma pessoa real conversando, não um robô.
- Frases curtas. No máximo 3 linhas por mensagem.
- No máximo 1 emoji por mensagem 🌿
- NUNCA use listas numeradas de opções ("1 - Sim / 2 - Não"). Pergunte de forma natural.
- Faça UMA pergunta por vez. Deixe a pessoa falar.
- Reaja ao que a pessoa disse antes de puxar o próximo assunto. Se ela contou algo difícil, acolha.
- NUNCA dê orientação jurídica, não prometa resultado, não fale de valores/honorários.
- NUNCA repita a saudação inicial nem pergunte o nome (já temos).
- Se perguntarem se você é humana ou IA, responda com honestidade em uma linha e siga a conversa.

════════════════════════════════
PERFIL "cliente" (paciente/familiar — HC para autocultivo)
════════════════════════════════
A pessoa JÁ FOI PERGUNTADA se tem prescrição médica. Sua primeira mensagem responde a isso.

CASO A — Ela NÃO tem prescrição médica (ou não vai conseguir agora):
Acolha, explique em linguagem simples que a prescrição médica é a base do pedido de HC, oriente a procurar um médico prescritor (muitos atendem por telemedicina) e convide a voltar quando tiver. Encerre com carinho.
Ao fazer isso, termine sua resposta com a tag [SEM_PRESCRICAO] e o bloco de resumo.

CASO B — Ela TEM prescrição médica:
Ótimo, o caso avança. Agora converse de verdade para entender a situação. Ao longo da conversa, de forma natural e sem parecer checklist, você precisa descobrir:
  • a condição de saúde / motivo do uso (sem pedir detalhe médico íntimo)
  • se ela já tem *laudo agronômico* do cultivo (ou se sabe o que é)
  • se já fez algum *curso de autocultivo*
  • qualquer urgência, medo ou situação específica que ela queira contar
Deixe a pessoa escrever à vontade. Se ela já contou algo, não pergunte de novo.
Quando tiver um retrato razoável do caso (normalmente em 3 a 5 trocas), agradeça, avise que vai encaminhar para a equipe e encerre com o bloco de resumo + [ATENDIMENTO_CONCLUIDO].

════════════════════════════════
PERFIL "palestra"
════════════════════════════════
Entenda: para qual público/instituição, formato desejado, previsão de data e o contato (e-mail ou telefone) para a equipe retornar. Converse naturalmente, sem formulário. Quando tiver o essencial, agradeça e encerre com resumo + [ATENDIMENTO_CONCLUIDO].

════════════════════════════════
PERFIL "profissional"
════════════════════════════════
Entenda: qual a profissão, onde atua, com que tipo de paciente, e o que exatamente busca (orientação para prescrever, consultoria para a clínica, dúvida regulatória). Converse naturalmente. Quando tiver o essencial, agradeça e encerre com resumo + [ATENDIMENTO_CONCLUIDO].

════════════════════════════════
COMO ENCERRAR (formato obrigatório)
════════════════════════════════
Ao encerrar, sua resposta deve ser: a mensagem de despedida para o lead, seguida do bloco abaixo.

[RESUMO_INICIO]
Escreva aqui, em até 5 linhas, um resumo objetivo para o ADVOGADO ler. Cubra apenas o que realmente apareceu na conversa: o que a pessoa procura, situação de saúde/contexto, se tem prescrição médica, se tem laudo agronômico, se fez curso de autocultivo, e qualquer detalhe relevante que ela contou. Sem emojis, sem enfeite, direto ao ponto. Nunca escreva "não se aplica" nem invente informação que não foi dita.
[RESUMO_FIM]
[ATENDIMENTO_CONCLUIDO]

Se o encerramento for por FALTA DE PRESCRIÇÃO MÉDICA, troque a tag final [ATENDIMENTO_CONCLUIDO] por [SEM_PRESCRICAO].

As tags são removidas antes de chegar ao lead — servem só para a equipe interna. Nunca use tag em mensagem que não seja de encerramento."""

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
                            "conditions": [{"id": "r3", "leftValue": "={{ $json.etapa }}", "rightValue": "menu",
                                            "operator": {"type": "string", "operation": "equals"}}],
                            "combinator": "and"},
             "renameOutput": True, "outputKey": "menu"},
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
nodes.append(code_node("Salvar Nome e Enviar Menu", CODE_NOME_MENU, "v2-nomemenu-0006", [-1300, -140]))
nodes.append(code_node("Processar Opcao do Menu", CODE_MENU, "v2-menu-0007", [-1300, 40]))
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
                "leftValue": "={{ $('Processar Resposta da IA').item.json.atendimentoFinalizado }}",
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
    "position": [-380, 240],
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
    "position": [60, 140],
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
                "leftValue": "={{ $('Processar Resposta da IA').item.json.qualificado }}",
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
    "position": [280, 140],
    "id": "v2-ifqual-0017",
    "name": "Lead Qualificado?",
})

NOTIF = (
    "=🌿 *Novo Lead - Simeao Advogados*\n\n"
    "Atendimento WhatsApp\n\n"
    "Nome: {{ $('Processar Resposta da IA').item.json.nome || 'Nao informado' }}\n"
    "WhatsApp: {{ $('Processar Resposta da IA').item.json.phone || 'Nao informado' }}\n"
    "Servico: {{ $('Processar Resposta da IA').item.json.servico || 'Nao informado' }}\n\n"
    "📋 *Resumo da conversa:*\n{{ $('Processar Resposta da IA').item.json.resumo || 'Sem resumo registrado' }}\n\n"
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
    "position": [500, 60],
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
        [{"node": "Salvar Nome e Enviar Menu", "type": "main", "index": 0}],
        [{"node": "Processar Opcao do Menu", "type": "main", "index": 0}],
        [{"node": "Preparar Contexto para IA", "type": "main", "index": 0}],
        [{"node": "Mensagem Pos Atendimento", "type": "main", "index": 0}],
        [{"node": "Montar Boas-vindas", "type": "main", "index": 0}],
    ]},
    "Mensagem Pos Atendimento": {"main": [[{"node": "Enviar mensagem cliente", "type": "main", "index": 0}]]},
    "Montar Boas-vindas": {"main": [[{"node": "Enviar mensagem cliente", "type": "main", "index": 0}]]},
    "Salvar Nome e Enviar Menu": {"main": [[{"node": "Enviar mensagem cliente", "type": "main", "index": 0}]]},
    "Processar Opcao do Menu": {"main": [[{"node": "Enviar mensagem cliente", "type": "main", "index": 0}]]},
    "Preparar Contexto para IA": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
    "AI Agent": {"main": [[{"node": "Processar Resposta da IA", "type": "main", "index": 0}]]},
    "Anthropic Chat Model": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
    "Postgres Chat Memory": {"ai_memory": [[{"node": "AI Agent", "type": "ai_memory", "index": 0}]]},
    "Processar Resposta da IA": {"main": [[{"node": "Enviar mensagem cliente", "type": "main", "index": 0}]]},
    "Enviar mensagem cliente": {"main": [[{"node": "Atendimento Finalizado?", "type": "main", "index": 0}]]},
    "Atendimento Finalizado?": {"main": [
        [{"node": "Montar Payload CRM", "type": "main", "index": 0}],
        [],
    ]},
    "Montar Payload CRM": {"main": [[{"node": "Enviar Lead para o CRM", "type": "main", "index": 0}]]},
    "Enviar Lead para o CRM": {"main": [[{"node": "Lead Qualificado?", "type": "main", "index": 0}]]},
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
