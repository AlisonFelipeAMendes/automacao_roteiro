"""
Metrics — Rastreamento em memória das métricas de execução do sistema.

Coleta dados de:
    - Fluxo diário (disparos, falhas)
    - Sessões (ativas, encerradas, expiradas)
    - Fluxo conversacional (CPF erros, pedidos aprovados, telemarketing)

Exposto via endpoint GET /status no webhook_handler.py.
"""

# ── PASSO 0: Imports ──────────────────────────────────────────────────────────
import json
from datetime import datetime
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Estrutura central de métricas (em memória)
# ─────────────────────────────────────────────────────────────────────────────

_STATS: dict[str, Any] = {
    # ── Controle de execução ─────────────────────────────────────────────────
    "servico_iniciado_em": None,          # datetime de startup
    "ultima_execucao_diaria": None,       # datetime do último fluxo diário

    # ── Fluxo diário ─────────────────────────────────────────────────────────
    "clientes_encontrados": 0,            # total consultado no roteiro
    "mensagens_enviadas_ok": 0,           # disparos com HTTP 200
    "mensagens_falhou": 0,               # disparos com erro Z-API

    # ── Sessões ──────────────────────────────────────────────────────────────
    "sessoes_criadas": 0,
    "sessoes_encerradas_ok": 0,          # concluídas normalmente
    "sessoes_encerradas_timeout": 0,     # expiradas por 5h
    "sessoes_encerradas_cpf": 0,         # encerradas por erro de CPF

    # ── Fluxo conversacional ─────────────────────────────────────────────────
    "cpf_erros_total": 0,               # total de erros de CPF (todas as sessões)
    "pedidos_aprovados": 0,
    "pedidos_cancelados": 0,
    "encaminhamentos_telemarketing": 0,

    # ── Webhook ──────────────────────────────────────────────────────────────
    "mensagens_recebidas": 0,            # total de POST /webhook recebidos
    "mensagens_fora_campanha": 0,        # ignoradas por não estar na campanha
}


# ─────────────────────────────────────────────────────────────────────────────
# API pública — incrementadores
# ─────────────────────────────────────────────────────────────────────────────

def registrar_inicio_servico() -> None:
    _STATS["servico_iniciado_em"] = datetime.now().isoformat()


def registrar_execucao_diaria(clientes: int) -> None:
    _STATS["ultima_execucao_diaria"] = datetime.now().isoformat()
    _STATS["clientes_encontrados"] = clientes


def incrementar(chave: str, valor: int = 1) -> None:
    """Incrementa uma métrica pelo nome da chave."""
    if chave in _STATS:
        _STATS[chave] += valor


def reset_stats_diarias() -> None:
    """
    Reseta os contadores diários antes de cada nova execução.
    Mantém servico_iniciado_em e ultima_execucao_diaria (serão sobrescritos).
    """
    chaves_diarias = [
        "clientes_encontrados", "mensagens_enviadas_ok", "mensagens_falhou",
        "sessoes_criadas", "sessoes_encerradas_ok", "sessoes_encerradas_timeout",
        "sessoes_encerradas_cpf", "cpf_erros_total", "pedidos_aprovados",
        "pedidos_cancelados", "encaminhamentos_telemarketing", "mensagens_recebidas",
        "mensagens_fora_campanha",
    ]
    for chave in chaves_diarias:
        _STATS[chave] = 0


def obter_stats() -> dict:
    """Retorna cópia das métricas atuais."""
    from src.core.session_manager import SESSIONS
    return {
        **_STATS,
        "sessoes_ativas_agora": len(SESSIONS),
    }


def imprimir_resumo() -> None:
    """Imprime um resumo formatado em ASCII no log/stdout."""
    stats = obter_stats()
    linhas = [
        "",
        "╔══════════════════════════════════════════════════════╗",
        "║         RESUMO DE EXECUÇÃO — AUTOMAÇÃO WHATSAPP      ║",
        "╠══════════════════════════════════════════════════════╣",
        f"║  Serviço iniciado em  : {stats['servico_iniciado_em'] or 'N/A':<30}║",
        f"║  Última execução      : {stats['ultima_execucao_diaria'] or 'N/A':<30}║",
        "╠══════════════════════════════════════════════════════╣",
        "║  DISPARO DIÁRIO                                      ║",
        f"║    Clientes no roteiro : {stats['clientes_encontrados']:<29}║",
        f"║    Mensagens enviadas  : {stats['mensagens_enviadas_ok']:<29}║",
        f"║    Falhas de envio     : {stats['mensagens_falhou']:<29}║",
        "╠══════════════════════════════════════════════════════╣",
        "║  SESSÕES                                             ║",
        f"║    Criadas             : {stats['sessoes_criadas']:<29}║",
        f"║    Ativas agora        : {stats['sessoes_ativas_agora']:<29}║",
        f"║    Encerradas (ok)     : {stats['sessoes_encerradas_ok']:<29}║",
        f"║    Encerradas (timeout): {stats['sessoes_encerradas_timeout']:<29}║",
        f"║    Encerradas (CPF)    : {stats['sessoes_encerradas_cpf']:<29}║",
        "╠══════════════════════════════════════════════════════╣",
        "║  FLUXO CONVERSACIONAL                                ║",
        f"║    Msgs recebidas      : {stats['mensagens_recebidas']:<29}║",
        f"║    Fora da campanha    : {stats['mensagens_fora_campanha']:<29}║",
        f"║    Erros de CPF        : {stats['cpf_erros_total']:<29}║",
        f"║    Pedidos aprovados   : {stats['pedidos_aprovados']:<29}║",
        f"║    Pedidos cancelados  : {stats['pedidos_cancelados']:<29}║",
        f"║    Telemarketing       : {stats['encaminhamentos_telemarketing']:<29}║",
        "╚══════════════════════════════════════════════════════╝",
        "",
    ]
    print("\n".join(linhas))
