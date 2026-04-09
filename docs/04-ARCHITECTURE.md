# Arquitetura Técnica

## Linguagem
Python 3.11+

## Bibliotecas
- pandas
- requests
- python-dotenv
- flask / fastapi para webhook

## Estrutura Projeto

src/
    config.py
    main.py

    integrations/
        whatsapp.py
        pedidos.py
        clientes_fake.py

    services/
        fluxo_service.py
        pedido_service.py

    core/
        session_manager.py
        state_machine.py

    webhook/
        webhook_handler.py

## Persistência

- Sessões podem ser armazenadas inicialmente em JSON/Memory.