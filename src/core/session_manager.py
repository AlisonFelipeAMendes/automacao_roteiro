"""
Session Manager — Gerencia sessões ativas em memória por número de telefone.

Cada sessão contém:
    - cliente        : dict com dados do cliente (COD_CLI, CPF/CNPJ, etc.)
    - state_machine  : instância de StateMachine para este cliente
    - pedido_temp    : lista mutável de itens do pedido sendo editado
    - tentativas_cpf : contador de erros de CPF (máx 2)
    - ultima_atividade : timestamp da última interação (para timeout de 5h)
    - item_em_edicao : código do produto sendo editado no momento (ou None)

Regras (09-GUARDRAILS.md):
    - Sessão expira após 5 horas sem resposta
    - Máximo de 2 erros de CPF
    - Apenas números da campanha possuem sessão
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import os


from src.core.metrics import incrementar
from src.core.state_machine import Estado, StateMachine

logger = logging.getLogger(__name__)

# ─── Constante de timeout ─────────────────────────────────────────────────────
TIMEOUT_HORAS: int = int(os.getenv("SESSION_TIMEOUT_HORAS", "6"))

# ─── Armazenamento global em memória ─────────────────────────────────────────
# Chave: número de telefone normalizado (ex: "5511999999999")
SESSIONS: dict[str, dict] = {}

# ─── Conjunto de números disparados na campanha do dia ───────────────────────
# Preenchido pelo main.py durante o disparo inicial
NUMEROS_CAMPANHA: set[str] = set()


# ─── Helpers de normalização ─────────────────────────────────────────────────

def normalizar_telefone(phone: str) -> str:
    """Remove qualquer caractere não numérico do número."""
    return "".join(c for c in phone if c.isdigit())


# ─── API pública do SessionManager ───────────────────────────────────────────

def criar_sessao(phone: str, cliente: dict, pedido_temp: list) -> dict:
    """
    Cria e registra uma nova sessão para o telefone informado.

    Args:
        phone       : número de telefone do cliente (será normalizado)
        cliente     : dict com dados do cliente do DataFrame
        pedido_temp : lista inicial de itens sugeridos (copiada defensivamente)

    Returns:
        dict da sessão criada
    """
    phone = normalizar_telefone(phone)
    sessao = {
        "phone": phone,
        "cliente": cliente,
        "state_machine": StateMachine(Estado.AGUARDANDO_CPF),
        "pedido_temp": list(pedido_temp),
        "tentativas_cpf": 0,
        "ultima_atividade": datetime.now(),
        "item_em_edicao": None,
    }
    SESSIONS[phone] = sessao
    NUMEROS_CAMPANHA.add(phone)
    incrementar("sessoes_criadas")
    logger.info("[SessionManager] Sessão criada para %s (cliente %s)", phone, cliente.get("COD_CLI"))
    return sessao


def obter_sessao(phone: str) -> Optional[dict]:
    """
    Retorna a sessão do número ou None se não existir / estiver expirada.
    Encerra automaticamente sessões expiradas.
    """
    phone = normalizar_telefone(phone)
    sessao = SESSIONS.get(phone)
    if sessao is None:
        return None

    if _expirada(sessao):
        logger.warning("[SessionManager] Sessão expirada para %s — encerrando.", phone)
        incrementar("sessoes_encerradas_timeout")
        encerrar_sessao(phone)
        return None

    return sessao


def atualizar_atividade(phone: str) -> None:
    """Atualiza o timestamp de última atividade (renova timeout)."""
    phone = normalizar_telefone(phone)
    if phone in SESSIONS:
        SESSIONS[phone]["ultima_atividade"] = datetime.now()


def atualizar_estado(phone: str, novo_estado: Estado) -> None:
    """Transita a state machine da sessão para o novo estado."""
    phone = normalizar_telefone(phone)
    sessao = SESSIONS.get(phone)
    if sessao:
        sessao["state_machine"].transitar(novo_estado)
        atualizar_atividade(phone)
        logger.debug("[SessionManager] %s → estado: %s", phone, novo_estado)


def encerrar_sessao(phone: str) -> None:
    """Remove a sessão da memória e registra no log."""
    phone = normalizar_telefone(phone)
    if phone in SESSIONS:
        try:
            SESSIONS[phone]["state_machine"].transitar(Estado.ENCERRADA)
        except ValueError:
            pass  # já estava encerrada
        del SESSIONS[phone]
        logger.info("[SessionManager] Sessão encerrada para %s", phone)


def sessao_ativa(phone: str) -> bool:
    """
    Retorna True se o número possui sessão válida e não expirada.
    Também verifica se o número pertence à campanha do dia.
    """
    phone = normalizar_telefone(phone)
    if phone not in NUMEROS_CAMPANHA:
        return False
    return obter_sessao(phone) is not None


def numero_na_campanha(phone: str) -> bool:
    """Verifica se o número foi disparado na campanha do dia."""
    return normalizar_telefone(phone) in NUMEROS_CAMPANHA


# ─── Privado ──────────────────────────────────────────────────────────────────

def _expirada(sessao: dict) -> bool:
    """Retorna True se a sessão passou do timeout de 5 horas."""
    limite = sessao["ultima_atividade"] + timedelta(hours=TIMEOUT_HORAS)
    return datetime.now() > limite