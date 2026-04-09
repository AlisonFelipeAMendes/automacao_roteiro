"""
Main — Orquestrador permanente da Automação Comercial Ativa WhatsApp.

Fluxo de execução:
    PASSO 1 → Carrega variáveis de ambiente (.env)
    PASSO 2 → Inicializa banco de histórico (SQLite)
    PASSO 3 → Sobe Webhook Z-API em thread daemon (porta 50001)
    PASSO 4 → Sobe Dashboard web em thread daemon   (porta 50000)
    PASSO 5 → Registra job diário no APScheduler
               → Executa imediatamente se EXECUTAR_AGORA=true
    PASSO 6 → Loop eterno — nunca encerra

Configurações via .env:
    DISPATCH_TIME=08:00          → horário diário do disparo (HH:MM)
    EXECUTAR_AGORA=true          → executa imediatamente ao iniciar
    SESSION_TIMEOUT_HORAS=6      → janela de resposta em horas
    WEBHOOK_PORT=50001
    DASHBOARD_PORT=50000

Execução diária (fluxo_diario):
    3.1 → Reseta métricas do dia
    3.2 → Consulta clientes fake (MVP) → trocar por consulta_roteiro_real()
    3.3 → Para cada cliente: pedidos reais → sessão → disparo Z-API
    3.4 → Imprime resumo e grava no histórico SQLite

O programa roda continuamente — o scheduler cuida de rodar todo dia.
"""

# ── PASSO 0: Imports stdlib ───────────────────────────────────────────────────
import logging
import os
import sys
import threading
import time

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# PASSO 1: Carrega .env ANTES de qualquer import do projeto
load_dotenv()
print("[PASSO 1] Variáveis de ambiente carregadas do .env")

# ── Imports do projeto (após load_dotenv) ─────────────────────────────────────
from src.core.history import init_db, salvar_execucao, registrar_cliente_disparado
from src.core.metrics import (
    imprimir_resumo,
    incrementar,
    obter_stats,
    registrar_execucao_diaria,
    registrar_inicio_servico,
    reset_stats_diarias,
)
from src.core.session_manager import criar_sessao
from src.dashboard.dashboard_app import dashboard as dashboard_app
from src.integrations.clientes_fake import consulta_cliente_fake  # ← trocar por consulta_roteiro_real() em produção
from src.integrations.whatsapp import enviar_texto
from src.services.fluxo_service import disparar_saudacao
from src.services.pedido_service import montar_sugestao_pedido
from src.webhook.webhook_handler import app as webhook_app

# ── Configuração de logging ───────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "..", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOGS_DIR, "automacao.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Parâmetros de configuração ────────────────────────────────────────────────
WEBHOOK_HOST    = os.getenv("WEBHOOK_HOST",   "0.0.0.0")
WEBHOOK_PORT    = int(os.getenv("WEBHOOK_PORT",    "50001"))
DASHBOARD_PORT  = int(os.getenv("DASHBOARD_PORT",  "50000"))
DISPATCH_TIME   = os.getenv("DISPATCH_TIME",  "08:00")   # HH:MM — horário do disparo diário
EXECUTAR_AGORA  = os.getenv("EXECUTAR_AGORA", "true").lower() == "true"

# Parse do horário de disparo
_hora, _minuto = DISPATCH_TIME.split(":")


# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3 — Webhook Z-API (porta 50001)
# ─────────────────────────────────────────────────────────────────────────────

def iniciar_webhook() -> None:
    """PASSO 3: Webhook Z-API — porta 50001. Recebe respostas dos clientes."""
    logger.info("[PASSO 3] Webhook Z-API iniciando em %s:%s", WEBHOOK_HOST, WEBHOOK_PORT)
    uvicorn.run(webhook_app, host=WEBHOOK_HOST, port=WEBHOOK_PORT, log_level="warning")


# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4 — Dashboard web (porta 50000)
# ─────────────────────────────────────────────────────────────────────────────

def iniciar_dashboard() -> None:
    """PASSO 4: Dashboard web — porta 50000. Painel de monitoramento."""
    logger.info("[PASSO 4] Dashboard iniciando em http://%s:%s", WEBHOOK_HOST, DASHBOARD_PORT)
    uvicorn.run(dashboard_app, host=WEBHOOK_HOST, port=DASHBOARD_PORT, log_level="warning")


# ─────────────────────────────────────────────────────────────────────────────
# PASSO 5 — Fluxo diário (agendado)
# ─────────────────────────────────────────────────────────────────────────────

def executar_fluxo_diario() -> None:
    """
    PASSO 5: Executa o disparo diário.
    Chamado pelo APScheduler todo dia no horário configurado em DISPATCH_TIME.
    Também é chamado imediatamente ao iniciar se EXECUTAR_AGORA=true.

    Passos internos:
        5.1 → Reseta contadores do dia
        5.2 → Consulta clientes sem atendimento
        5.3 → Para cada cliente: pedidos → sessão → disparo
        5.4 → Salva histórico e imprime resumo
    """
    logger.info("=" * 60)
    logger.info("[PASSO 5] Iniciando fluxo diário de automação")
    logger.info("=" * 60)

    # PASSO 5.1 — Reseta métricas do dia anterior
    reset_stats_diarias()
    logger.info("[PASSO 5.1] Métricas do dia zeradas")

    # PASSO 5.2 — Consulta clientes sem atendimento
    # MVP:      consulta_cliente_fake()   ← em uso
    # Produção: consulta_roteiro_real()   ← trocar aqui
    logger.info("[PASSO 5.2] Consultando clientes sem atendimento presencial")
    clientes_df = consulta_cliente_fake()
    total = len(clientes_df)
    logger.info("[PASSO 5.2] %s cliente(s) encontrado(s)", total)
    registrar_execucao_diaria(total)

    if total == 0:
        logger.info("[PASSO 5.2] Nenhum cliente no roteiro hoje.")
        imprimir_resumo()
        salvar_execucao(obter_stats())
        return

    # PASSO 5.3 — Processa cada cliente
    for idx, row in clientes_df.iterrows():
        cliente = row.to_dict()
        phone = str(cliente.get("TELEFONE_A", "")).strip()
        cod_cli = cliente.get("COD_CLI", "N/A")

        logger.info("[PASSO 5.3] Cliente %s/%s | COD_CLI: %s | phone: %s", idx + 1, total, cod_cli, phone)

        if not phone:
            logger.warning("[PASSO 5.3] COD_CLI %s sem TELEFONE_A — pulado.", cod_cli)
            continue

        # PASSO 5.3.1 — Pedidos reais
        logger.info("[PASSO 5.3.1] Consultando pedidos para COD_CLI %s", cod_cli)
        pedido_temp = montar_sugestao_pedido(str(cod_cli))
        logger.info("[PASSO 5.3.1] %s item(ns) na sugestão", len(pedido_temp))

        # PASSO 5.3.2 — Cria sessão
        logger.info("[PASSO 5.3.2] Criando sessão para %s", phone)
        criar_sessao(phone, cliente, pedido_temp)

        # PASSO 5.3.3 — Dispara saudação via Z-API
        logger.info("[PASSO 5.3.3] Disparando saudação para %s", phone)
        saudacao = disparar_saudacao(phone, cliente)
        try:
            status, _ = enviar_texto(phone, saudacao)
            logger.info("[PASSO 5.3.3] HTTP %s → %s", status, phone)
            incrementar("mensagens_enviadas_ok")
            registrar_cliente_disparado(cliente, phone, "OK")
        except Exception as exc:
            logger.error("[PASSO 5.3.3] Falha ao enviar para %s: %s", phone, exc)
            incrementar("mensagens_falhou")
            registrar_cliente_disparado(cliente, phone, "FALHA")

        time.sleep(1)  # respeita rate limit Z-API

    # PASSO 5.4 — Salva histórico e mostra resumo
    logger.info("[PASSO 5.4] Salvando execução no histórico")
    stats = obter_stats()
    salvar_execucao(stats)
    imprimir_resumo()
    logger.info("[PASSO 5] Fluxo diário concluído. %s cliente(s) processado(s).", total)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    registrar_inicio_servico()

    # PASSO 2 — Inicializa banco de histórico
    print("[PASSO 2] Inicializando banco de histórico SQLite...")
    init_db()

    # PASSO 3 — Webhook Z-API em thread daemon (porta 50001)
    print(f"[PASSO 3] Subindo webhook Z-API na porta {WEBHOOK_PORT}...")
    threading.Thread(target=iniciar_webhook, daemon=True).start()

    # PASSO 4 — Dashboard em thread daemon (porta 50000)
    print(f"[PASSO 4] Subindo dashboard web na porta {DASHBOARD_PORT}...")
    threading.Thread(target=iniciar_dashboard, daemon=True).start()

    time.sleep(2)  # aguarda servers inicializarem

    # PASSO 5 — Scheduler diário
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        executar_fluxo_diario,
        CronTrigger(hour=int(_hora), minute=int(_minuto)),
        id="fluxo_diario",
        max_instances=1,
        misfire_grace_time=300,  # tolera até 5 min de atraso
    )
    scheduler.start()
    logger.info(
        "[PASSO 5] Scheduler ativo — fluxo diário agendado para %s (todo dia).",
        DISPATCH_TIME,
    )

    # Executa imediatamente se configurado
    if EXECUTAR_AGORA:
        logger.info("[PASSO 5] EXECUTAR_AGORA=true — executando agora...")
        executar_fluxo_diario()

    # PASSO 6 — Loop eterno — o programa nunca encerra
    logger.info("[PASSO 6] Sistema permanente ativo.")
    logger.info("[PASSO 6] Dashboard: http://localhost:%s", DASHBOARD_PORT)
    logger.info("[PASSO 6] Webhook:   http://localhost:%s/webhook", WEBHOOK_PORT)
    logger.info("[PASSO 6] Próximo disparo: %s (todo dia). Ctrl+C para encerrar.", DISPATCH_TIME)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown(wait=False)
        logger.info("[ENCERRAMENTO] Sistema encerrado manualmente.")