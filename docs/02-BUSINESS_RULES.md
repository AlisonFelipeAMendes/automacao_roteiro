# Regras de Negócio

## Consulta Inicial

- A consulta de clientes sem atendimento será FAKE durante MVP.
- A consulta de pedidos será REAL utilizando API SQL existente.

## Regra de Disparo

- Apenas clientes retornados na consulta fake poderão receber mensagem ativa.

## Regra de Resposta

- Apenas números previamente disparados poderão receber resposta do bot.

## Validação CPF/CNPJ

- Cliente deve informar os 5 primeiros dígitos do CPF/CNPJ.
- Máximo de 2 tentativas.

## Timeout

- Sessão expira após 5 horas sem resposta.

## Fluxo de Atendimento

Após validação:
1. Atendimento Telemarketing
2. Sugestão de Pedido

## Fluxo Telemarketing

- Registrar solicitação em arquivo/log e criar um arquivo auxiliar que irá printar a resposta, futuramente receberar nova função.

## Fluxo Sugestão

- Enviar pedido sugerido.
- Permitir:
    - Aprovar pedido
    - Alterar quantidade
    - Cancelar

## Regra de Alteração

- Alteração item a item.
- Listar todos os itens e quantidade a cada nova edição
- Após cada alteração perguntar se deseja editar novo item.