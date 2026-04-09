"""
Webhook Handler — Receptor de mensagens Z-API via FastAPI.

Responsabilidades:
    - Expor endpoint POST /webhook para receber mensagens do WhatsApp
    - Validar estrutura do payload Z-API
    - Extrair phone e texto da mensagem
    - Ignorar mensagens fora da campanha (guardrail silencioso)
    - Despachar para fluxo_service.processar_mensagem()
    - Retornar resposta via enviar_texto()

Payload esperado Z-API (estrutura padrão):
{
    "phone": "5511999999999",
    "text": { "message": "Olá" },
    ...
}
"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.core.metrics import obter_stats
from src.integrations.whatsapp import enviar_texto
from src.services.fluxo_service import processar_mensagem

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Automação Comercial Ativa — Webhook",
    description="Receptor de mensagens WhatsApp via Z-API",
    version="1.0.0",
)


@app.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
    """
    Recebe eventos de mensagens da Z-API.

    A Z-API dispara este endpoint toda vez que o número recebe uma mensagem.
    Apenas mensagens de números que estão na campanha ativa serão processadas.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload JSON inválido.")

    # ── Extração do phone ─────────────────────────────────────────────────────
    phone: str = data.get("phone", "")
    if not phone:
        logger.warning("[Webhook] Payload sem campo 'phone': %s", data)
        return JSONResponse({"status": "ignored", "reason": "sem phone"}, status_code=200)

    # ── Extração do texto ─────────────────────────────────────────────────────
    # Z-API pode mandar texto em data["text"]["message"] ou data["message"]
    texto: str = ""
    if isinstance(data.get("text"), dict):
        texto = data["text"].get("message", "")
    elif isinstance(data.get("message"), str):
        texto = data["message"]

    if not texto:
        logger.info("[Webhook] Mensagem sem texto de %s — ignorada.", phone)
        return JSONResponse({"status": "ignored", "reason": "sem texto"}, status_code=200)

    logger.info("[Webhook] Mensagem recebida | phone: %s | texto: %s", phone, texto)

    # ── Processar fluxo ───────────────────────────────────────────────────────
    resposta = processar_mensagem(phone, texto)

    if resposta is None:
        # Número fora da campanha — silêncio (guardrail)
        return JSONResponse({"status": "ignored", "reason": "fora da campanha"}, status_code=200)

    # ── Enviar resposta via WhatsApp ──────────────────────────────────────────
    try:
        status_code, resp_text = enviar_texto(phone, resposta)
        logger.info("[Webhook] Resposta enviada para %s | HTTP %s", phone, status_code)
    except Exception as exc:
        logger.error("[Webhook] Falha ao enviar mensagem para %s: %s", phone, exc)
        return JSONResponse(
            {"status": "error", "reason": "falha ao enviar whatsapp"},
            status_code=500,
        )

    return JSONResponse({"status": "ok", "phone": phone}, status_code=200)


@app.get("/health")
async def health_check() -> JSONResponse:
    """Endpoint de health check para monitoramento."""
    return JSONResponse({"status": "running"})


@app.get("/status")
async def status() -> JSONResponse:
    """
    Retorna métricas completas do sistema:
        - Dados do último disparo diário
        - Número de sessões ativas
        - Totais de mensagens enviadas, falhas, CPF erros, pedidos, telemarketing
    """
    return JSONResponse(obter_stats())