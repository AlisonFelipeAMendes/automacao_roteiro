"""
State Machine — Define estados válidos e transições do fluxo conversacional.

Estados:
    AGUARDANDO_CPF              → sessão criada, aguardando os 5 primeiros dígitos
    AGUARDANDO_MENU             → CPF validado, aguardando escolha do menu (1 ou 2)
    AGUARDANDO_ITEM_EDICAO      → cliente escolheu editar pedido, aguardando código do produto
    AGUARDANDO_QUANTIDADE       → aguardando nova quantidade de um item
    AGUARDANDO_CONTINUAR_EDICAO → item atualizado, perguntando se deseja editar outro
    AGUARDANDO_CONFIRMACAO      → pedido apresentado, aguardando aprovação/cancelamento
    ENCERRADA                   → sessão finalizada (por conclusão, erro de CPF ou timeout)
"""

from enum import Enum


class Estado(str, Enum):
    AGUARDANDO_CPF = "AGUARDANDO_CPF"
    AGUARDANDO_MENU = "AGUARDANDO_MENU"
    AGUARDANDO_ITEM_EDICAO = "AGUARDANDO_ITEM_EDICAO"
    AGUARDANDO_QUANTIDADE = "AGUARDANDO_QUANTIDADE"
    AGUARDANDO_CONTINUAR_EDICAO = "AGUARDANDO_CONTINUAR_EDICAO"
    AGUARDANDO_CONFIRMACAO = "AGUARDANDO_CONFIRMACAO"
    ENCERRADA = "ENCERRADA"


# Transições válidas: estado_atual -> lista de próximos estados permitidos
TRANSICOES_VALIDAS: dict[Estado, list[Estado]] = {
    Estado.AGUARDANDO_CPF: [
        Estado.AGUARDANDO_MENU,
        Estado.ENCERRADA,
    ],
    Estado.AGUARDANDO_MENU: [
        Estado.AGUARDANDO_ITEM_EDICAO,
        Estado.AGUARDANDO_CONFIRMACAO,
        Estado.ENCERRADA,
    ],
    Estado.AGUARDANDO_ITEM_EDICAO: [
        Estado.AGUARDANDO_QUANTIDADE,
        Estado.AGUARDANDO_MENU,
        Estado.ENCERRADA,
    ],
    Estado.AGUARDANDO_QUANTIDADE: [
        Estado.AGUARDANDO_CONTINUAR_EDICAO,
        Estado.ENCERRADA,
    ],
    Estado.AGUARDANDO_CONTINUAR_EDICAO: [
        Estado.AGUARDANDO_ITEM_EDICAO,
        Estado.AGUARDANDO_CONFIRMACAO,
        Estado.ENCERRADA,
    ],
    Estado.AGUARDANDO_CONFIRMACAO: [
        Estado.AGUARDANDO_ITEM_EDICAO,
        Estado.ENCERRADA,
    ],
    Estado.ENCERRADA: [],
}


class StateMachine:
    """Gerencia o estado atual da sessão e valida transições."""

    def __init__(self, estado_inicial: Estado = Estado.AGUARDANDO_CPF):
        self.estado_atual: Estado = estado_inicial

    def transitar(self, novo_estado: Estado) -> None:
        """Realiza transição validada para o novo estado."""
        permitidos = TRANSICOES_VALIDAS.get(self.estado_atual, [])
        if novo_estado not in permitidos:
            raise ValueError(
                f"Transição inválida: {self.estado_atual} -> {novo_estado}. "
                f"Permitidos: {permitidos}"
            )
        self.estado_atual = novo_estado

    def obter_estado(self) -> Estado:
        return self.estado_atual

    def esta_encerrada(self) -> bool:
        return self.estado_atual == Estado.ENCERRADA