# Especificação Funcional

## Fluxo Diário

1. Executar consulta_cliente_fake().
2. Salvar DataFrame clientes.
3. Consultar pedidos reais para cada cliente.
4. Salvar DataFrame pedidos.
5. Disparar mensagem ativa.

## Fluxo Webhook

1. Receber mensagem.
2. Validar número remetente.
3. Validar sessão ativa.
4. Processar estado atual.

## Fluxo de Identificação

1. Solicitar CPF/CNPJ parcial.
2. Validar 5 primeiros dígitos.
3. Se correto avançar.
4. Se incorreto incrementar tentativa.
5. Se tentativa > 2 encerrar.

## Fluxo Sugestão Pedido

1. Montar sugestão baseada em pedidos.
2. Enviar itens.
3. Solicitar ação.

## Fluxo Edição Pedido

1. Perguntar item.
2. Perguntar nova quantidade.
3. Atualizar pedido temporário.
4. Perguntar se deseja continuar editando.