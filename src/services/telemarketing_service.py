"""
Telemarketing Service — Registra encaminhamentos para a equipe de telemarketing.

Responsabilidades:
    - Gravar log persistente em logs/telemarketing.log
    - Criar arquivo auxiliar logs/telemarketing_pendente.txt (um por disparo)
      que futuramente receberá nova função (ex: integração com CRM)

Regra (02-BUSINESS_RULES.md):
    "Registrar solicitação em arquivo/log e criar um arquivo auxiliar
     que irá printar a resposta, futuramente receberá nova função."
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Paths dos arquivos de log ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
TELEMARKETING_LOG = os.path.join(LOGS_DIR, "telemarketing.log")
TELEMARKETING_PENDENTE = os.path.join(LOGS_DIR, "telemarketing_pendente.txt")


def _garantir_logs_dir() -> None:
    """Cria o diretório de logs se não existir."""
    os.makedirs(LOGS_DIR, exist_ok=True)


def registrar_telemarketing(cliente: dict, phone: str) -> None:
    """
    Registra a solicitação de telemarketing em log persistente e arquivo auxiliar.

    Args:
        cliente : dict com dados do cliente da sessão
        phone   : número de telefone que solicitou telemarketing
    """
    _garantir_logs_dir()

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cod_cli = cliente.get("COD_CLI", "N/A")
    cod_vendedor = cliente.get("COD_VENDEDOR", "N/A")

    entrada_log = (
        f"[{agora}] TELEMARKETING | "
        f"Phone: {phone} | "
        f"COD_CLI: {cod_cli} | "
        f"COD_VENDEDOR: {cod_vendedor}\n"
    )

    # ── Log persistente (append) ──────────────────────────────────────────────
    with open(TELEMARKETING_LOG, "a", encoding="utf-8") as f:
        f.write(entrada_log)

    # ── Arquivo auxiliar (sobrescreve com o mais recente) ─────────────────────
    conteudo_pendente = (
        f"=== PENDENTE TELEMARKETING ===\n"
        f"Data/Hora  : {agora}\n"
        f"Telefone   : {phone}\n"
        f"COD_CLI    : {cod_cli}\n"
        f"COD_VENDEDOR: {cod_vendedor}\n"
        f"{'=' * 30}\n"
    )
    with open(TELEMARKETING_PENDENTE, "a", encoding="utf-8") as f:
        f.write(conteudo_pendente)

    logger.info("[Telemarketing] Encaminhamento registrado para %s (cliente %s)", phone, cod_cli)
    print(conteudo_pendente)  # print conforme especificação de 02-BUSINESS_RULES.md
