import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from src.integrations.clientes_fake import consulta_cliente_fake, consulta_roteiro_real
from src.core.session_manager import criar_sessao
from src.services.fluxo_service import processar_mensagem, disparar_saudacao

print("=" * 60)
print("VALIDANDO formato dos dados fake e CPF formatado")
print("=" * 60)

# PASSO 1 — Valida clientes fake
df = consulta_cliente_fake()
cliente = df.iloc[0].to_dict()
print(f"\nCliente retornado:")
for k, v in cliente.items():
    print(f"  {k}: {v!r}")

assert cliente["COD_VENDEDOR"] == 657, "COD_VENDEDOR deve ser int 657"
assert cliente["COD_CLI"] == 1001, "COD_CLI deve ser int 1001"
assert cliente["CPF/CNPJ"] == "321.546.132-88", "CPF/CNPJ errado"
assert cliente["TELEFONE_A"] == "559181973164", "Telefone errado"
print("\n[OK] Formato dos dados fake esta correto")

# PASSO 2 — Valida que as duas funcoes existem
from src.integrations.clientes_fake import consulta_cliente_fake, consulta_roteiro_real
print("[OK] Ambas as funcoes existem: consulta_cliente_fake() e consulta_roteiro_real()")

# PASSO 3 — Valida CPF formatado na validacao do fluxo
phone = cliente["TELEFONE_A"]  # "559181973164"
pedido_fake = [{"codproduto": "PROD001", "qt": 5, "preco_unitario": 10.0, "preco_total": 50.0}]
criar_sessao(phone, cliente, pedido_fake)

# CPF "321.546.132-88" → normalizado "32154613288" → prefixo "32154"
# Cliente deve enviar "32154"
resp_errado = processar_mensagem(phone, "00000")
assert "incorreto" in resp_errado.lower(), f"Deveria rejeitar CPF errado: {resp_errado}"
print(f"[OK] CPF errado rejeitado corretamente")

# Recria sessao (anterior encerrou em 1a tentativa errada, temos 1 restante)
# Vamos testar o correto diretamente numa nova sessao
phone2 = "5591981973164"  # TELEFONE_B
criar_sessao(phone2, cliente, pedido_fake)

resp_certo = processar_mensagem(phone2, "32154")  # 5 primeiros digitos de "321.546.132-88"
assert "confirmada" in resp_certo.lower() or "sugestao" in resp_certo.lower() or "pedido" in resp_certo.lower(), \
    f"CPF correto nao avancou: {resp_certo}"
print(f"[OK] CPF formatado '321.546.132-88' validado com entrada '32154' com sucesso!")

# PASSO 4 — Valida saudacao
msg = disparar_saudacao(phone, cliente)
assert "1001" in msg or "distribuidora" in msg.lower(), f"Saudacao incorreta: {msg}"
print(f"[OK] Saudacao gerada corretamente ({len(msg)} chars)")

print("\n" + "=" * 60)
print("TODOS OS TESTES PASSARAM!")
print("=" * 60)
