import requests
import pandas as pd
from src.config import URL_CONSULTA, PASSWORD, TIMEOUT

def consulta_pedidos(codcliente: str):
    sql = f"""
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