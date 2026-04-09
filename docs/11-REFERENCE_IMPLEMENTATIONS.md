# Implementações de Referência

## Objetivo

Este documento contém implementações já existentes e homologadas.
Toda nova implementação deve seguir estes padrões base.

---

# Integração WhatsApp Oficial

## Biblioteca
requests

## Provedor
Z-API

## Implementação Base Obrigatória

```python
import requests
import os

INSTANCE_ID = os.getenv("INSTANCE_ID")
TOKEN = os.getenv("TOKEN")
CLIENT_TOKEN = os.getenv("CLIENT_TOKEN")

BASE_URL = f"https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}"

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


import requests
import pandas as pd

def executar_consulta(sql: str):

    payload = {
        "password": PASSWORD,
        "sql": sql
    }

    response = requests.post(
        URL_CONSULTA,
        json=payload,
        timeout=TIMEOUT
    )

    data = response.json()

    return pd.DataFrame(
        data["rows"],
        columns=data["columns"]
    )

# Pedidos
   SQL_QUERY_PEDIDOS = f"""
        SELECT
            codfilial,
            codvendedor,
            codcliente,
            dtmov,
            codoperacao,
            numpedido,
            codproduto,
            CASE 
                WHEN qt = 0 THEN 0
                ELSE ptabela / qt
            END AS preco_unitario,
            qt,
            ptabela AS preco_total
        FROM vw_f_vendas
        WHERE codcliente = '{codcliente}'
        AND codoperacao = 'V'
        AND dtmov >= ADD_MONTHS(TRUNC(SYSDATE), -6)
        ORDER BY dtmov DESC
        """
 

SQL_QUERY_ROTEIRO = """
        SELECT
            R.COD_VENDEDOR,
            R.COD_CLI,
            cli.cgcent,
            R.VISITADO,
            TRUNC(R.DATA) AS DT_ROTEIRO,
            -------- DATA DA ULTIMA VENDA 
            (
                SELECT MAX(MV.DTMOV)
                FROM PCMOV MV
                WHERE MV.CODCLI   = R.COD_CLI
                AND MV.CODCLI = CODCLI
                AND MV.DTCANCEL IS NULL
            )  AS DT_ULTIMA_VENDA,
            (CLI.TELENT) AS TELEFONE_A,
            (CLI.TELCOB) AS TELEFONE_B
            
            
            
            ----------- ROTEIRO DO DIA ANTERIOR
        FROM ROTA_FV_NUVEM R
        JOIN PCCLIENT CLI ON CLI.CODCLI = R.cod_cli
        WHERE  R.VISITADO     = 'N'
        AND TRUNC(R.DATA)  = TRUNC(SYSDATE) - 1
        AND R.COD_CLI NOT IN (
                SELECT DISTINCT PED.CODCLI
                    FROM PCPEDC PED
                    JOIN PCPEDI PI ON PED.NUMPED = PI.NUMPED
                    WHERE PED.DTCANCEL  IS NULL
                    AND PED.CONDVENDA  IN (1, 8)
                    AND PED.POSICAO   <> 'C'
                    AND PED.CODUSUR    = 657
                    AND PED.DATA BETWEEN TRUNC(SYSDATE, 'MM')
                                    AND LAST_DAY(SYSDATE)
                    AND PED.CODCLI    IS NOT NULL
            )
            
        ORDER BY DT_ULTIMA_VENDA ASC NULLS FIRST,
                R.COD_CLI

        """