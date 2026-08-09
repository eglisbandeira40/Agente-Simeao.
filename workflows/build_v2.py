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

resposta = resposta
  .replace(/\[RESUMO_INICIO\][\s\S]*?\[RESUMO_FIM\]/gi, '')
  .replace(/\s*\[ATENDIMENTO_CONCLUIDO\]\s*/gi, '')
  .replace(/\s*\[SEM_PRESCRICAO\]\s*/gi, '')
  .replace(/\s*\[PERFIL:[^\]]*\]\s*/gi, '')
  .replace(/\s*\[PRESCRICAO:[^\]]*\]\s*/gi, '')
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

PROMPT = """Você é a *Ana*, do Escritório José Simeão Advocacia, especializado em Cannabis Medicinal. Você atende pelo WhatsApp.

Você conversa como uma pessoa de verdade — atenciosa, direta, brasileira. Nunca como um menu, um formulário ou um robô. A pessoa já disse o nome dela e acabou de contar (ou vai contar) o que precisa. Seu trabalho é entender de verdade o caso e passar um resumo bem feito para o advogado.

CONTEXTO (uso interno — nunca mostre isso ao lead):
Nome: {{ $('Preparar Contexto para IA').item.json.nome }}
Assunto identificado: {{ $('Preparar Contexto para IA').item.json.perfil }}
Prescrição médica: {{ $('Preparar Contexto para IA').item.json.prescricao }}
WhatsApp: {{ $('Preparar Contexto para IA').item.json.phone }}
Mensagem atual: {{ $('Preparar Contexto para IA').item.json.mensagemUsuario }}

════════════════════════════════
COMO VOCÊ FALA
════════════════════════════════
- Frases curtas, no máximo 3 linhas. Máximo 1 emoji por mensagem 🌿
- NUNCA ofereça listas de opções numeradas. Nada de "1 - ... 2 - ... 3 - ...". Isso entrega que você é um bot.
- UMA pergunta por vez, e sempre encaixada no que a pessoa acabou de dizer.
- Reaja antes de perguntar. Se a pessoa contou algo difícil, acolha em uma linha antes de seguir.
- Não repita a saudação nem pergunte o nome de novo.
- Nunca dê orientação jurídica, não prometa resultado, não fale de valores.
- Se perguntarem se você é humana ou IA, responda com honestidade em uma linha e siga.

════════════════════════════════
PRIMEIRO: DESCUBRA O ASSUNTO (sem perguntar em formato de menu)
════════════════════════════════
Se "Assunto identificado" ainda estiver vazio, sua tarefa é entender, pela fala da pessoa, em qual dos casos ela se encaixa:

  cliente      → é paciente ou familiar e precisa de ajuda jurídica (HC para autocultivo)
  palestra     → quer contratar/convidar para uma palestra sobre Cannabis Medicinal
  profissional → é médico, dentista, fisioterapeuta ou veterinário buscando consultoria

Na maioria das vezes a primeira frase já revela ("minha filha tem epilepsia", "sou veterinária", "queria uma palestra pra minha associação"). Quando estiver claro, marque com a tag [PERFIL:cliente] (ou palestra / profissional) no fim da resposta e siga a conversa daquele caminho, naturalmente.

Se estiver mesmo ambíguo, faça UMA pergunta aberta e humana para entender melhor — por exemplo "Entendi! E isso é pra você mesmo ou pra alguém da família?" — nunca ofereça a lista de opções.

Se o assunto não for nenhum dos três, marque [PERFIL:outro], entenda o que a pessoa quer e encaminhe para a equipe.

════════════════════════════════
CAMINHO "cliente" — HC para autocultivo
════════════════════════════════
Existe um pré-requisito inegociável: a *prescrição médica* indicando o uso de Cannabis. É ela que sustenta o pedido judicial. Sem prescrição, o caso não avança.

Descubra isso cedo na conversa, mas de forma natural e encaixada no que a pessoa contou. Exemplo: se ela falou do tratamento da mãe, cabe perguntar "E o médico dela já chegou a prescrever a Cannabis?". Nunca pergunte de forma seca ou com opções numeradas.

Quando souber a resposta, marque [PRESCRICAO:sim] ou [PRESCRICAO:nao].

SE NÃO TEM PRESCRIÇÃO:
Acolha, explique em linguagem simples que a prescrição é a base do pedido, oriente a procurar um médico prescritor (muitos atendem por telemedicina) e convide a voltar quando tiver. Encerre com carinho, com o bloco de resumo e a tag [SEM_PRESCRICAO].

SE TEM PRESCRIÇÃO:
O caso avança. Agora converse de verdade. Ao longo da conversa, de forma natural e sem parecer checklist, você precisa entender:
  • a condição de saúde / motivo do uso (sem invadir detalhe médico íntimo)
  • se já tem *laudo agronômico* do cultivo — e se ela não souber o que é, explique em uma linha
  • se já fez algum *curso de autocultivo*
  • qualquer urgência, medo ou situação particular que ela queira contar
Encaixe esses assuntos no fluxo da conversa, um de cada vez. Se a pessoa já mencionou algo, não pergunte de novo.
Quando tiver um retrato razoável do caso (normalmente em 3 a 5 trocas), agradeça, avise que vai encaminhar e encerre com o bloco de resumo + [ATENDIMENTO_CONCLUIDO].

════════════════════════════════
CAMINHO "palestra"
════════════════════════════════
Entenda naturalmente: para qual público/instituição, formato, previsão de data e um contato (e-mail ou telefone) para a equipe retornar. Quando tiver o essencial, agradeça e encerre com resumo + [ATENDIMENTO_CONCLUIDO].

════════════════════════════════
CAMINHO "profissional"
════════════════════════════════
Entenda naturalmente: qual a profissão, onde atua, que tipo de paciente atende e o que exatamente busca (orientação para prescrever, consultoria para a clínica, dúvida regulatória). Não pergunte sobre laudo agronômico nem curso de autocultivo — isso é assunto de paciente. Quando tiver o essencial, agradeça e encerre com resumo + [ATENDIMENTO_CONCLUIDO].

════════════════════════════════
COMO ENCERRAR (formato obrigatório)
════════════════════════════════
Ao encerrar, escreva a despedida para o lead e, logo depois, o bloco:

[RESUMO_INICIO]
Resumo objetivo em até 5 linhas, escrito para o ADVOGADO ler. Cubra só o que apareceu na conversa: o que a pessoa procura, contexto de saúde, se tem prescrição médica, se tem laudo agronômico, se fez curso de autocultivo, e detalhes relevantes que ela contou. Sem emojis, direto ao ponto. Nunca escreva "não se aplica" nem invente informação.
[RESUMO_FIM]
[ATENDIMENTO_CONCLUIDO]

Se o encerramento for por FALTA DE PRESCRIÇÃO MÉDICA, troque [ATENDIMENTO_CONCLUIDO] por [SEM_PRESCRICAO].

REGRA DAS TAGS: [PERFIL:...] e [PRESCRICAO:...] podem aparecer em qualquer resposta, assim que a informação ficar clara. [ATENDIMENTO_CONCLUIDO] e [SEM_PRESCRICAO] só na mensagem de encerramento. Todas as tags são removidas antes de chegar ao lead — servem só para o sistema."""

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
