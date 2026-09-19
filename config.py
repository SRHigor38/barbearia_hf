# ============================================
# CONFIGURAÇÕES DA APLICAÇÃO
# ============================================
# Centraliza todas as configurações do Flask em um só lugar.

import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env (apenas no ambiente local)
load_dotenv()


class Config:
    """
    Classe de configuração do Flask.
    As configurações são acessadas via app.config.from_object().
    """

    # Chave secreta para assinar cookies, sessões e tokens CSRF
    # Em produção (Render) vem de variável de ambiente com generateValue.
    # O fallback existe apenas para desenvolvimento local.
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-key")

    # Cookies de sessão endurecidos (produção exige HTTPS no Render)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("APP_ENV", "development") == "production"

    # Limite global de upload (fotos de profissionais: 2MB)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024

    # ============================================
    # BANCO DE DADOS
    # ============================================
    # Usa a variável de ambiente DATABASE_URL quando definida.
    # Em desenvolvimento local, pode ser SQLite ou PostgreSQL local.
    # Em produção, a plataforma de hospedagem fornece DATABASE_URL.
    #
    # Exemplos:
    #   SQLite:     sqlite:///caminho/para/barbearia.db
    #   PostgreSQL: postgresql://usuario:senha@host:5432/barbearia
    #
    # Se DATABASE_URL não estiver definida, usa SQLite local (desenvolvimento).
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    if DATABASE_URL:
        # Normaliza a URL do PostgreSQL se necessário
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        if DATABASE_URL.startswith("postgresql://") and "+psycopg2" not in DATABASE_URL:
            # Garante o uso do driver psycopg2 (recomendado)
            DATABASE_URL = DATABASE_URL.replace(
                "postgresql://", "postgresql+psycopg2://", 1
            )

        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Fallback: SQLite local (apenas desenvolvimento)
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "barbearia.db"
        )

    # Desativa o rastreamento de modificações do SQLAlchemy (economiza memória)
    SQLALCHEMY_TRACK_MODIFICATIONS = False