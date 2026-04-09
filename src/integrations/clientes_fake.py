"""
Integração de Clientes — Roteiro Diário

Contém DUAS funções para buscar clientes sem atendimento:

    consulta_cliente_fake()   ← USADA AGORA no MVP
    consulta_roteiro_real()   ← FUTURA função de produção (SQL homologado)

Para ir a produção: troque a chamada em main.py, linha comentada com "← trocar".
"""

# ── PASSO 0: Imports ──────────────────────────────────────────────────────────
import logging
from datetime import datetime, timedelta

import pandas as pd
import requests

from src.config import PASSWORD, TIMEOUT, URL_CONSULTA

logger = logging.getLogger(__name__)


# =============================================================================
# FUNÇÃO 1 — FAKE  (em uso no MVP)
# =============================================================================

def consulta_cliente_fake() -> pd.DataFrame:
    """
    PASSO 1A — Retorna clientes fake para o MVP.

    Simula o retorno da consulta de roteiro:
    clientes que estavam no roteiro do dia anterior mas NÃO foram visitados.

    Formato idêntico ao retorno real de consulta_roteiro_real().
    CPF/CNPJ mantido no formato original com pontos e traços —
    a normalização (só dígitos) é feita na validação em fluxo_service.py.
    """
    logger.info("[PASSO 1A] Executando consulta FAKE de clientes sem atendimento")

    data = [
        {
            "COD_VENDEDOR": 657,
            "COD_CLI": 1001,
            "VISITADO": "N",
            "CPF/CNPJ": "321.546.132-88",
            "DT_ROTEIRO": (datetime.now() - timedelta(days=1)).date(),
            "DT_ULTIMA_VENDA": (datetime.now() - timedelta(days=30)).date(),
            "TELEFONE_A": "559180379443",
            "TELEFONE_B": "559180379443",
        },
        {
            "COD_VENDEDOR": 657,
            "COD_CLI": 1002,
            "VISITADO": "N",
            "CPF/CNPJ": "000.639.142-71",
            "DT_ROTEIRO": (datetime.now() - timedelta(days=1)).date(),
            "DT_ULTIMA_VENDA": (datetime.now() - timedelta(days=30)).date(),
            "TELEFONE_A": "559181973164",
            "TELEFONE_B": "5591981973164",
        }
    ]

    df = pd.DataFrame(data)
    logger.info("[PASSO 1A] %s cliente(s) no roteiro fake", len(df))
    return df


# =============================================================================
# FUNÇÃO 2 — REAL  (produção futura — não alterar o SQL)
# =============================================================================

# SQL homologado em 11-REFERENCE_IMPLEMENTATIONS.md — não alterar
_SQL_QUERY_ROTEIRO = """
    SELECT
        R.COD_VENDEDOR,
        R.COD_CLI,
        cli.cgcent AS "CPF/CNPJ",
        R.VISITADO,
        TRUNC(R.DATA)  AS DT_ROTEIRO,
        (
            SELECT MAX(MV.DTMOV)
            FROM PCMOV MV
            WHERE MV.CODCLI  = R.COD_CLI
              AND MV.DTCANCEL IS NULL
        ) AS DT_ULTIMA_VENDA,
        (CLI.TELENT) AS TELEFONE_A,
        (CLI.TELCOB) AS TELEFONE_B
    FROM ROTA_FV_NUVEM R
    JOIN PCCLIENT CLI ON CLI.CODCLI = R.cod_cli
    WHERE  R.VISITADO    = 'N'
      AND TRUNC(R.DATA)  = TRUNC(SYSDATE) - 1
      AND R.COD_CLI NOT IN (
            SELECT DISTINCT PED.CODCLI
            FROM PCPEDC PED
            JOIN PCPEDI PI ON PED.NUMPED = PI.NUMPED
            WHERE PED.DTCANCEL   IS NULL
              AND PED.CONDVENDA  IN (1, 8)
              AND PED.POSICAO   <> 'C'
              AND PED.CODUSUR    = 657
              AND PED.DATA BETWEEN TRUNC(SYSDATE, 'MM') AND LAST_DAY(SYSDATE)
              AND PED.CODCLI    IS NOT NULL
      )
    ORDER BY DT_ULTIMA_VENDA ASC NULLS FIRST, R.COD_CLI
"""


def consulta_roteiro_real() -> pd.DataFrame:
    """
    PASSO 1B — Consulta clientes reais sem atendimento via API SQL.

    Usa SQL_QUERY_ROTEIRO homologado em 11-REFERENCE_IMPLEMENTATIONS.md.
    Retorna DataFrame com as mesmas colunas da versão fake.

    ⚠️ Para ativar em produção, edite main.py:
           consulta_cliente_fake()  →  consulta_roteiro_real()
    """
    logger.info("[PASSO 1B] Executando consulta REAL de roteiro via API SQL")

    # PASSO 1B.1 — Monta payload
    payload = {
        "password": PASSWORD,
        "sql": _SQL_QUERY_ROTEIRO,
    }

    # PASSO 1B.2 — Chama API SQL
    try:
        response = requests.post(URL_CONSULTA, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("[PASSO 1B] Falha na consulta real do roteiro: %s", exc)
        return pd.DataFrame()

    # PASSO 1B.3 — Converte para DataFrame
    data = response.json()
    df = pd.DataFrame(data["rows"], columns=data["columns"])
    logger.info("[PASSO 1B] %s cliente(s) encontrado(s) no roteiro real", len(df))
    return df