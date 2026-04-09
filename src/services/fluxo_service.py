"""
Fluxo Service — Processamento central das mensagens recebidas via webhook.

Responsabilidades:
    - Receber mensagem do cliente (phone + texto)
    - Validar número na campanha (guardrail 09-GUARDRAILS.md)
    - Avaliar estado atual da sessão
    - Despachar para o handler específico do estado
    - Retornar resposta textual a ser enviada via WhatsApp

Guardrails obrigatórios implementados:
    ✅ Não responder números fora da campanha
    ✅ Nunca avançar fluxo sem validação CPF (máx 2 tentativas)
    ✅ Não quebrar fluxo por input inválido — responde com orientação
    ✅ Sessão expirada tratada automaticamente pelo session_manager
"""

import logging
from typing import Optional

from src.core.history import registrar_mensagem
from src.core.metrics import incrementar
from src.core.session_manager import (
    atualizar_estado,
    encerrar_sessao,
    numero_na_campanha,
    obter_sessao,
)
from src.core.state_machine import Estado
from src.services.pedido_service import (
    aplicar_edicao,
    formatar_pedido_atualizado,
    formatar_sugestao_mensagem,
    listar_itens_para_edicao,
)
from src.services.telemarketing_service import registrar_telemarketing

logger = logging.getLogger(__name__)

# ─── Limite de tentativas de CPF (09-GUARDRAILS.md) ──────────────────────────
MAX_TENTATIVAS_CPF: int = 2


# ─── Ponto de entrada ─────────────────────────────────────────────────────────

def processar_mensagem(phone: str, texto: str) -> Optional[str]:
    """
    Processa uma mensagem recebida e retorna a resposta a ser enviada.

    Returns:
        Texto de resposta ou None (se o número não deve receber resposta)
    """
    texto = texto.strip()

    # Métrica: total de mensagens recebidas pelo webhook
    incrementar("mensagens_recebidas")

    # ── Guardrail: somente números da campanha ────────────────────────────────
    if not numero_na_campanha(phone):
        logger.warning("[FluxoService] Número %s fora da campanha — ignorado.", phone)
        incrementar("mensagens_fora_campanha")
        return None

    sessao = obter_sessao(phone)

    # ── Sessão expirada ou inexistente ────────────────────────────────────────
    if sessao is None:
        logger.info("[FluxoService] Sessão expirada ou inexistente para %s.", phone)
        return (
            "⏰ Sua sessão expirou ou já foi encerrada. "
            "Caso precise de ajuda, entre em contato pelo nosso canal de atendimento."
        )

    cod_cli = str(sessao["cliente"].get("COD_CLI", ""))
    estado  = sessao["state_machine"].obter_estado()
    logger.debug("[FluxoService] %s | estado: %s | msg: %s", phone, estado, texto)

    # Log da mensagem recebida do cliente
    registrar_mensagem(phone, cod_cli, "RECEBIDA", texto, str(estado))

    # ── Despacho por estado ───────────────────────────────────────────────────
    handlers = {
        Estado.AGUARDANDO_CPF: _handle_aguardando_cpf,
        Estado.AGUARDANDO_MENU: _handle_aguardando_menu,
        Estado.AGUARDANDO_ITEM_EDICAO: _handle_aguardando_item_edicao,
        Estado.AGUARDANDO_QUANTIDADE: _handle_aguardando_quantidade,
        Estado.AGUARDANDO_CONTINUAR_EDICAO: _handle_aguardando_continuar_edicao,
        Estado.AGUARDANDO_CONFIRMACAO: _handle_aguardando_confirmacao,
    }

    handler = handlers.get(estado)
    if handler is None:
        logger.error("[FluxoService] Estado sem handler: %s", estado)
        return "Ocorreu um erro interno. Sua sessão será encerrada."

    resposta = handler(phone, texto, sessao)

    # Log da resposta enviada ao cliente
    if resposta:
        estado_pos = sessao["state_machine"].obter_estado()
        registrar_mensagem(phone, cod_cli, "ENVIADA", resposta, str(estado_pos))

    return resposta


# ─── Handlers por estado ──────────────────────────────────────────────────────

def _handle_aguardando_cpf(phone: str, texto: str, sessao: dict) -> str:
    """
    Valida os 5 primeiros dígitos do CPF/CNPJ informado pelo cliente.
    Após 2 erros a sessão é encerrada.
    """
    # PASSO 2.1 — Busca CPF/CNPJ do cliente (coluna "CPF/CNPJ" conforme DB)
    cliente = sessao["cliente"]
    cpf_cnpj_completo: str = str(cliente.get("CPF/CNPJ", ""))

    # PASSO 2.2 — Normaliza CPF/CNPJ: remove pontos, traços e barras
    # Ex: "321.546.132-88" → "32154613288" → primeiros 5 = "32154"
    cpf_apenas_digitos = "".join(c for c in cpf_cnpj_completo if c.isdigit())
    prefixo_esperado = cpf_apenas_digitos[:5]

    # PASSO 2.3 — Normaliza entrada do cliente (apenas dígitos)
    entrada = "".join(c for c in texto if c.isdigit())

    if entrada == prefixo_esperado:
        atualizar_estado(phone, Estado.AGUARDANDO_MENU)
        msg_sugestao = formatar_sugestao_mensagem(sessao["pedido_temp"])
        logger.info("[FluxoService] CPF validado para %s", phone)
        return (
            f"✅ Identidade confirmada! Olá, *{cliente.get('COD_CLI', 'cliente')}*.\n\n"
            + msg_sugestao
        )

    # CPF errado
    sessao["tentativas_cpf"] += 1
    tentativas = sessao["tentativas_cpf"]
    logger.warning("[FluxoService] CPF errado para %s (tentativa %s/%s)", phone, tentativas, MAX_TENTATIVAS_CPF)

    if tentativas >= MAX_TENTATIVAS_CPF:
        encerrar_sessao(phone)
        incrementar("sessoes_encerradas_cpf")
        return (
            "❌ CPF/CNPJ incorreto por 2 vezes. "
            "Por segurança, encerramos sua sessão. "
            "Entre em contato pelo nosso canal de atendimento."
        )

    incrementar("cpf_erros_total")

    restantes = MAX_TENTATIVAS_CPF - tentativas
    return (
        f"⚠️ CPF/CNPJ incorreto. Você tem mais {restantes} tentativa(s).\n"
        "Por favor, informe os *5 primeiros dígitos* do seu CPF ou CNPJ:"
    )


def _handle_aguardando_menu(phone: str, texto: str, sessao: dict) -> str:
    """
    Processa escolha do menu principal:
        1 = Atendimento Telemarketing
        2 = Sugestão de Pedido (já exibida)
    """
    op = texto.strip()

    if op == "1":
        # ── Telemarketing ────────────────────────────────────────────────────
        registrar_telemarketing(sessao["cliente"], phone)
        encerrar_sessao(phone)
        incrementar("encaminhamentos_telemarketing")
        incrementar("sessoes_encerradas_ok")
        return (
            "📞 Sua solicitação foi registrada! "
            "Em breve nossa equipe de telemarketing entrará em contato. "
            "Tenha um ótimo dia! 😊"
        )

    if op == "2":
        # ── Sugestão de pedido ───────────────────────────────────────────────
        if not sessao["pedido_temp"]:
            encerrar_sessao(phone)
            return "Não há itens na sugestão de pedido. Encerrando atendimento."
        atualizar_estado(phone, Estado.AGUARDANDO_CONFIRMACAO)
        return (
            "📦 Sua sugestão de pedido está pronta!\n\n"
            + formatar_sugestao_mensagem(sessao["pedido_temp"])
        )

    if op == "3":
        # ── Cancelar ─────────────────────────────────────────────────────────
        encerrar_sessao(phone)
        incrementar("sessoes_encerradas_ok")
        return "Atendimento encerrado. Obrigado! 👋"

    # Input inválido — não quebra o fluxo (guardrail)
    return (
        "❓ Opção não reconhecida. Escolha:\n"
        "1️⃣  Telemarketing\n"
        "2️⃣  Sugestão de pedido\n"
        "3️⃣  Cancelar"
    )


def _handle_aguardando_confirmacao(phone: str, texto: str, sessao: dict) -> str:
    """
    Processa confirmação final do pedido sugerido:
        1 = Aprovar
        2 = Editar quantidade
        3 = Cancelar
    """
    op = texto.strip()

    if op == "1":
        # Aprovar pedido
        pedido = sessao["pedido_temp"]
        logger.info("[FluxoService] Pedido aprovado por %s: %s", phone, pedido)
        encerrar_sessao(phone)
        incrementar("pedidos_aprovados")
        incrementar("sessoes_encerradas_ok")
        return (
            "✅ *Pedido aprovado!* Obrigado!\n"
            "Nossa equipe processará seu pedido em breve. 🚚"
        )

    if op == "2":
        # Editar
        atualizar_estado(phone, Estado.AGUARDANDO_ITEM_EDICAO)
        return listar_itens_para_edicao(sessao["pedido_temp"])

    if op == "3":
        # Cancelar
        encerrar_sessao(phone)
        incrementar("pedidos_cancelados")
        incrementar("sessoes_encerradas_ok")
        return "❌ Pedido cancelado. Atendimento encerrado. Até logo! 👋"

    # Input inválido
    return (
        "❓ Opção inválida. Responda:\n"
        "1️⃣  Aprovar pedido\n"
        "2️⃣  Editar quantidade\n"
        "3️⃣  Cancelar"
    )


def _handle_aguardando_item_edicao(phone: str, texto: str, sessao: dict) -> str:
    """
    Recebe o código do produto que o cliente quer editar.
    Valida se o produto existe no pedido antes de avançar.
    """
    codproduto = texto.strip().upper()
    pedido = sessao["pedido_temp"]

    # Verifica se o código existe no pedido
    existe = any(item["codproduto"].upper() == codproduto for item in pedido)
    if not existe:
        return (
            f"⚠️ Produto *{codproduto}* não encontrado no pedido.\n\n"
            + listar_itens_para_edicao(pedido)
        )

    sessao["item_em_edicao"] = codproduto
    atualizar_estado(phone, Estado.AGUARDANDO_QUANTIDADE)
    qt_atual = next(
        item["qt"] for item in pedido if item["codproduto"].upper() == codproduto
    )
    return (
        f"✏️ Produto: *{codproduto}* | Quantidade atual: *{qt_atual}*\n"
        "Informe a *nova quantidade* (0 para remover o item):"
    )


def _handle_aguardando_quantidade(phone: str, texto: str, sessao: dict) -> str:
    """
    Recebe a nova quantidade para o item em edição e aplica a mudança.
    Após edição, lista o pedido atualizado e pergunta se deseja continuar editando.
    """
    codproduto = sessao.get("item_em_edicao")
    if not codproduto:
        atualizar_estado(phone, Estado.AGUARDANDO_ITEM_EDICAO)
        return "Ocorreu um erro. Por favor, informe o produto novamente."

    # Valida se é número inteiro
    if not texto.strip().isdigit():
        return "⚠️ Por favor, informe apenas o número da quantidade (ex: 10):"

    nova_qt = int(texto.strip())
    sucesso, erro = aplicar_edicao(sessao["pedido_temp"], codproduto, nova_qt)

    if not sucesso:
        return f"⚠️ {erro}\nInforme a quantidade novamente:"

    sessao["item_em_edicao"] = None
    atualizar_estado(phone, Estado.AGUARDANDO_CONTINUAR_EDICAO)

    pedido_formatado = formatar_pedido_atualizado(sessao["pedido_temp"])
    return (
        f"✅ Produto *{codproduto}* atualizado!\n\n"
        + pedido_formatado
        + "\n\nDeseja editar outro item?\n"
        "1️⃣  Sim, editar outro\n"
        "2️⃣  Não, confirmar pedido"
    )


def _handle_aguardando_continuar_edicao(phone: str, texto: str, sessao: dict) -> str:
    """
    Pergunta se o cliente quer editar mais um item ou confirmar o pedido.
    """
    op = texto.strip()

    if op == "1":
        atualizar_estado(phone, Estado.AGUARDANDO_ITEM_EDICAO)
        return listar_itens_para_edicao(sessao["pedido_temp"])

    if op == "2":
        atualizar_estado(phone, Estado.AGUARDANDO_CONFIRMACAO)
        return (
            formatar_sugestao_mensagem(sessao["pedido_temp"])
        )

    return (
        "❓ Responda:\n"
        "1️⃣  Sim, editar outro item\n"
        "2️⃣  Não, confirmar pedido"
    )


# ─── Disparo inicial (chamado por main.py) ────────────────────────────────────

def disparar_saudacao(phone: str, cliente: dict) -> str:
    """
    Monta a mensagem de saudação inicial enviada durante o disparo diário.
    """
    nome_cli = cliente.get("COD_CLI", "cliente")
    return (
        f"Olá! 👋 Somos da *Olinda Distribuidora*.\n\n"
        f"Notamos que o representante comercial não pôde visitar você ontem, "
        f"cliente *{nome_cli}*.\n\n"
        "Para darmos continuidade ao seu atendimento, precisamos confirmar sua identidade.\n\n"
        "Por favor, informe os *5 primeiros dígitos* do seu CPF ou CNPJ:"
    )