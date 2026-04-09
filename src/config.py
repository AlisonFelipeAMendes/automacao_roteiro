# Configurações globais do projeto
import os

INSTANCE_ID = os.getenv("INSTANCE_ID")
TOKEN = os.getenv("TOKEN")
CLIENT_TOKEN = os.getenv("CLIENT_TOKEN")

BASE_URL = f"https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}"

TIMEOUT = 30
URL_CONSULTA = os.getenv("URL_CONSULTA")
PASSWORD = os.getenv("PASSWORD")