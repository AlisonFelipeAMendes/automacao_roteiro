import requests
from src.config import BASE_URL, CLIENT_TOKEN

HEADERS = {
    "Content-Type": "application/json",
    "Client-Token": CLIENT_TOKEN
}

def enviar_texto(phone: str, texto: str):
    url = f"{BASE_URL}/send-messages"

    payload = {
        "phone": phone,
        "message": texto
    }

    response = requests.post(
        url,
        json=payload,
        headers=HEADERS
    )

    return response.status_code, response.text