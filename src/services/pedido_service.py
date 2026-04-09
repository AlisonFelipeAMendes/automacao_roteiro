"""
Pedido Service — Monta, formata e edita sugestões de pedido.

Responsabilidades:
    - Construir sugestão de pedido a partir do histórico real (DataFrame)
    - Formatar a sugestão como mensagem WhatsApp legível
    - Aplicar edições item a item (guardrail: item a item conforme 02-BUSINESS_RULES.md)
    - Listar pedido atualizado após cada edição
"""

import logging
from typing import Optional

import pandas as pd

from src.integrations.pedidos import consulta_pedidos

logger = logging.getLogger(__name__)


# ─── Builder ─────────────────────────────────────────────────────────────────

def montar_sugestao_pedido(codcliente: str) -> list[dict]:
    """
    Consulta o histórico real de pedidos e monta sugestão baseada em médias.

    Agrupamento do último pedido por produto, preservando preço unitário,
    ordenado por quantidade decrescente.

    Returns:
        Lista de dicts com chaves: codproduto, qt, preco_unitario, preco_total
    """
    try:
        df = consulta_pedidos(codcliente)
    except Exception as exc:
        logger.error("[PedidoService] Erro ao consultar pedidos de %s: %s", codcliente, exc)
        return []

    if df.empty:
        logger.info("[PedidoService] Sem histórico de pedidos para cliente %s", codcliente)
        return []

    # Converter colunas numéricas
    for col in ("qt", "preco_unitario", "preco_total"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Agrupa por produto: soma quantidades, média de preço unitário
    agrupado = (
        df.groupby("codproduto")
        .agg(qt=("qt", "sum"), preco_unitario=("preco_unitario", "mean"))
        .reset_index()
    )
    agrupado["qt"] = agrupado["qt"].astype(int)
    agrupado["preco_unitario"] = agrupado["preco_unitario"].round(2)
    agrupado["preco_total"] = (agrupado["qt"] * agrupado["preco_unitario"]).round(2)

    # Ordena por quantidade desc
    agrupado = agrupado.sort_values("qt", ascending=False)

    return agrupado.to_dict(orient="records")


# ─── Formatação de mensagens ──────────────────────────────────────────────────

def formatar_sugestao_mensagem(sugestao: list[dict]) -> str:
    """
    Formata a lista de itens como mensagem de texto para WhatsApp.

    Exemplo de saída:
        📦 *Sugestão de Pedido*

        1. Produto: ABC123 | Qtd: 10 | Unitário: R$ 5,00 | Total: R$ 50,00
        2. Produto: XYZ456 | Qtd: 5  | Unitário: R$ 12,00 | Total: R$ 60,00

        Total geral: R$ 110,00

        Escolha uma opção:
        1️⃣  Aprovar pedido
        2️⃣  Editar quantidade
        3️⃣  Cancelar
    """
    if not sugestao:
        return "Não encontramos pedidos anteriores para sugerir. Deseja falar com nosso telemarketing? (1-Sim / 2-Não)"

    linhas = ["📦 *Sugestão de Pedido*\n"]
    total_geral = 0.0

    for i, item in enumerate(sugestao, start=1):
        preco_unit = item.get("preco_unitario", 0)
        qt = item.get("qt", 0)
        total = item.get("preco_total", preco_unit * qt)
        total_geral += total
        linhas.append(
            f"{i}. Produto: *{item['codproduto']}* | "
            f"Qtd: {qt} | "
            f"Unitário: R$ {preco_unit:.2f} | "
            f"Total: R$ {total:.2f}"
        )

    linhas.append(f"\n💰 *Total geral: R$ {total_geral:.2f}*")
    linhas.append(
        "\nEscolha uma opção:\n"
        "1️⃣  Aprovar pedido\n"
        "2️⃣  Editar quantidade\n"
        "3️⃣  Cancelar"
    )
    return "\n".join(linhas)


def formatar_pedido_atualizado(sugestao: list[dict]) -> str:
    """
    Lista os itens atuais do pedido após uma edição.
    Usado para mostrar estado completo antes de perguntar se edita mais.
    """
    if not sugestao:
        return "⚠️ Nenhum item no pedido."

    linhas = ["📋 *Pedido atualizado:*\n"]
    total_geral = 0.0

    for i, item in enumerate(sugestao, start=1):
        preco_unit = item.get("preco_unitario", 0)
        qt = item.get("qt", 0)
        total = round(preco_unit * qt, 2)
        item["preco_total"] = total
        total_geral += total
        linhas.append(
            f"{i}. *{item['codproduto']}* — Qtd: {qt} | Total: R$ {total:.2f}"
        )

    linhas.append(f"\n💰 *Total: R$ {total_geral:.2f}*")
    return "\n".join(linhas)


# ─── Editor de itens ─────────────────────────────────────────────────────────

def listar_itens_para_edicao(sugestao: list[dict]) -> str:
    """
    Lista os itens com numeração para o cliente escolher qual editar.
    """
    if not sugestao:
        return "Nenhum item disponível para edição."

    linhas = ["✏️ *Qual produto deseja editar?*\n", "Digite o código do produto:\n"]
    for item in sugestao:
        linhas.append(f"🔹 *{item['codproduto']}* — Qtd atual: {item['qt']}")
    return "\n".join(linhas)


def aplicar_edicao(
    sugestao: list[dict],
    codproduto: str,
    nova_qt: int,
) -> tuple[bool, Optional[str]]:
    """
    Atualiza a quantidade de um produto na sugestão.

    Args:
        sugestao   : lista mutável de itens do pedido
        codproduto : código do produto a editar
        nova_qt    : nova quantidade (>= 0; 0 = remove o item)

    Returns:
        (sucesso, mensagem_de_erro)
    """
    for item in sugestao:
        if item["codproduto"].upper() == codproduto.upper():
            if nova_qt < 0:
                return False, "A quantidade não pode ser negativa."
            if nova_qt == 0:
                sugestao.remove(item)
                logger.info("[PedidoService] Item %s removido do pedido.", codproduto)
            else:
                item["qt"] = nova_qt
                item["preco_total"] = round(nova_qt * item.get("preco_unitario", 0), 2)
                logger.info("[PedidoService] Item %s → qtd %s", codproduto, nova_qt)
            return True, None

    return False, f"Produto *{codproduto}* não encontrado no pedido."