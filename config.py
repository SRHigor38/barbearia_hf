# ============================================
# CONFIGURAÇÕES DA APLICAÇÃO
# ============================================
# Centraliza todas as configurações do Flask em um só lugar.

import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()


class Config:
    """
    Classe de configuração do Flask.
    As configurações são acessadas via app.config.from_object().
    """

    # Chave secreta para assinar cookies, sessões e tokens CSRF
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-key")

    # Caminho do banco de dados SQLite
    # "sqlite:///" + caminho absoluto para o arquivo .db
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "barbearia.db"
    )

    # Desativa o rastreamento de modificações do SQLAlchemy (economiza memória)
    SQLALCHEMY_TRACK_MODIFICATIONS = False