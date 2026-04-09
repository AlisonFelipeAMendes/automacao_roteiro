"""
History — Persistência completa em SQLite.

Banco de dados: logs/history.db

Tabelas:
    execution_history   → resumo de cada execução diária
    conversa_log        → histórico de mensagens por cliente/telefone
    clientes_disparados → clientes que receberam disparo em cada execução
"""

import csv
import io
import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Caminho do banco ─────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(_BASE_DIR, "logs", "history.db")


# ─────────────────────────────────────────────────────────────────────────────
# INICIALIZAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Cria o banco e todas as tabelas se não existirem."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:

        # Tabela 1 — Resumo de execuções diárias
        conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_history (
                id                            INTEGER PRIMARY KEY AUTOINCREMENT,
                data_execucao                 TEXT NOT NULL,
                hora_execucao                 TEXT NOT NULL,
                clientes_encontrados          INTEGER DEFAULT 0,
                mensagens_enviadas            INTEGER DEFAULT 0,
                mensagens_falhou              INTEGER DEFAULT 0,
                sessoes_criadas               INTEGER DEFAULT 0,
                sessoes_encerradas_ok         INTEGER DEFAULT 0,
                sessoes_encerradas_timeout    INTEGER DEFAULT 0,
                sessoes_encerradas_cpf        INTEGER DEFAULT 0,
                cpf_erros_total               INTEGER DEFAULT 0,
                pedidos_aprovados             INTEGER DEFAULT 0,
                pedidos_cancelados            INTEGER DEFAULT 0,
                encaminhamentos_telemarketing INTEGER DEFAULT 0,
                mensagens_recebidas           INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        # Tabela 2 — Log de conversas por cliente
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversa_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                data_execucao TEXT NOT NULL,
                phone         TEXT NOT NULL,
                cod_cli       TEXT,
                direcao       TEXT NOT NULL,  -- 'RECEBIDA' | 'ENVIADA'
                mensagem      TEXT,
                estado        TEXT,
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        # Tabela 3 — Clientes disparados por execução
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clientes_disparados (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                data_execucao  TEXT NOT NULL,
                hora_execucao  TEXT NOT NULL,
                phone          TEXT,
                cod_cli        TEXT,
                cod_vendedor   TEXT,
                cpf_cnpj       TEXT,
                telefone_b     TEXT,
                dt_ultima_venda TEXT,
                status_envio   TEXT,   -- 'OK' | 'FALHA'
                created_at     TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        conn.commit()
    logger.info("[History] Banco inicializado em %s", DB_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# TABELA: execution_history
# ─────────────────────────────────────────────────────────────────────────────

def salvar_execucao(stats: dict) -> None:
    """Persiste o resumo de uma execução diária."""
    now = datetime.now()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO execution_history (
                    data_execucao, hora_execucao,
                    clientes_encontrados, mensagens_enviadas, mensagens_falhou,
                    sessoes_criadas, sessoes_encerradas_ok, sessoes_encerradas_timeout,
                    sessoes_encerradas_cpf, cpf_erros_total, pedidos_aprovados,
                    pedidos_cancelados, encaminhamentos_telemarketing, mensagens_recebidas
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
                stats.get("clientes_encontrados", 0),
                stats.get("mensagens_enviadas_ok", 0),
                stats.get("mensagens_falhou", 0),
                stats.get("sessoes_criadas", 0),
                stats.get("sessoes_encerradas_ok", 0),
                stats.get("sessoes_encerradas_timeout", 0),
                stats.get("sessoes_encerradas_cpf", 0),
                stats.get("cpf_erros_total", 0),
                stats.get("pedidos_aprovados", 0),
                stats.get("pedidos_cancelados", 0),
                stats.get("encaminhamentos_telemarketing", 0),
                stats.get("mensagens_recebidas", 0),
            ))
            conn.commit()
        logger.info("[History] Execução salva: %s", now.strftime("%Y-%m-%d %H:%M"))
    except Exception as exc:
        logger.error("[History] Falha ao salvar execução: %s", exc)


def buscar_historico(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    limit: int = 60,
) -> list[dict]:
    """Retorna execuções filtradas por período (mais recentes primeiro)."""
    query = "SELECT * FROM execution_history WHERE 1=1"
    params: list = []
    if data_inicio:
        query += " AND data_execucao >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND data_execucao <= ?"
        params.append(data_fim)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return _fetchall(query, params)


# ─────────────────────────────────────────────────────────────────────────────
# TABELA: conversa_log
# ─────────────────────────────────────────────────────────────────────────────

def registrar_mensagem(
    phone: str,
    cod_cli: str,
    direcao: str,
    mensagem: str,
    estado: str = "",
) -> None:
    """
    Grava uma mensagem no log de conversas.

    Args:
        direcao: 'RECEBIDA' (cliente → bot) | 'ENVIADA' (bot → cliente)
    """
    data = datetime.now().strftime("%Y-%m-%d")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO conversa_log (data_execucao, phone, cod_cli, direcao, mensagem, estado)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (data, phone, str(cod_cli), direcao, mensagem, estado))
            conn.commit()
    except Exception as exc:
        logger.error("[History] Falha ao registrar mensagem: %s", exc)


def buscar_conversas(
    phone: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    cod_cli: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    """Retorna histórico de conversas com filtros opcionais."""
    query = "SELECT * FROM conversa_log WHERE 1=1"
    params: list = []
    if phone:
        query += " AND phone = ?"
        params.append(phone)
    if cod_cli:
        query += " AND cod_cli = ?"
        params.append(str(cod_cli))
    if data_inicio:
        query += " AND data_execucao >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND data_execucao <= ?"
        params.append(data_fim)
    query += " ORDER BY id ASC LIMIT ?"
    params.append(limit)
    return _fetchall(query, params)


def listar_clientes_com_conversa() -> list[dict]:
    """Retorna lista de clientes únicos com conversas registradas."""
    query = """
        SELECT phone, cod_cli,
               MIN(data_execucao) as primeira_conversa,
               MAX(data_execucao) as ultima_conversa,
               COUNT(*) as total_mensagens
        FROM conversa_log
        GROUP BY phone, cod_cli
        ORDER BY ultima_conversa DESC
    """
    return _fetchall(query, [])


# ─────────────────────────────────────────────────────────────────────────────
# TABELA: clientes_disparados
# ─────────────────────────────────────────────────────────────────────────────

def registrar_cliente_disparado(cliente: dict, phone: str, status: str) -> None:
    """
    Registra um cliente que recebeu (ou tentou receber) o disparo.

    Args:
        status: 'OK' | 'FALHA'
    """
    now = datetime.now()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO clientes_disparados (
                    data_execucao, hora_execucao, phone, cod_cli, cod_vendedor,
                    cpf_cnpj, telefone_b, dt_ultima_venda, status_envio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                phone,
                str(cliente.get("COD_CLI", "")),
                str(cliente.get("COD_VENDEDOR", "")),
                cliente.get("CPF/CNPJ", ""),
                cliente.get("TELEFONE_B", ""),
                str(cliente.get("DT_ULTIMA_VENDA", "")),
                status,
            ))
            conn.commit()
    except Exception as exc:
        logger.error("[History] Falha ao registrar cliente disparado: %s", exc)


def buscar_clientes_disparados(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Retorna clientes disparados filtrados por período."""
    query = "SELECT * FROM clientes_disparados WHERE 1=1"
    params: list = []
    if data_inicio:
        query += " AND data_execucao >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND data_execucao <= ?"
        params.append(data_fim)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return _fetchall(query, params)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fetchall(query: str, params: list) -> list[dict]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as exc:
        logger.error("[History] Falha na consulta: %s", exc)
        return []
