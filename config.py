# ============================================
# CONFIGURAÇÕES DA APLICAÇÃO
# ============================================
# Centraliza todas as configurações do Flask em um só lugar.

import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env (apenas no ambiente local)
load_dotenv()


# ============================================
# AMBIENTE: LOCAL (desenvolvimento) x PRODUÇÃO
# ============================================
# LOCAL / DESENVOLVIMENTO:
#   - Pode usar SQLite (barbearia.db). Cômodo para rodar e testar na máquina.
#
# PRODUÇÃO (Render e afins):
#   - OBRIGATORIAMENTE PostgreSQL através da variável DATABASE_URL.
#   - NUNCA usar SQLite: o disco da plataforma é efêmero, então o arquivo
#     .db é perdido a cada restart/sleep/redeploy, causando perda de dados
#     (agendamentos, clientes, planos, profissionais, serviços, financeiro).
#
# A produção é reconhecida por QUALQUER um destes sinais:
#   - APP_ENV=production  (definido no render.yaml)
#   - RENDER=true         (o Render define esta variável automaticamente)
#   - PRODUCTION=true     (outras plataformas de hospedagem)


def _booleano(valor):
    """Interpreta flags de ambiente: 1/true/yes/on -> True."""
    return str(valor or "").strip().lower() in ("1", "true", "yes", "on")


MSG_SEM_DATABASE_URL = (
    "CONFIGURACAO INVALIDA: a aplicacao iniciou em PRODUCAO sem DATABASE_URL.\n"
    "Em producao o banco DEVE ser PostgreSQL: o disco da plataforma e efemero\n"
    "e o SQLite seria apagado no proximo restart/sleep, perdendo os dados de\n"
    "agendamentos, clientes, planos, profissionais, servicos e financeiro.\n"
    "COMO CORRIGIR NO RENDER: Dashboard > Web Service > Environment >\n"
    "adicionar a variavel DATABASE_URL do PostgreSQL do Render\n"
    "(Add from database > connectionString) ou aplicar o render.yaml.\n"
    "Ver README.md > Producao (PostgreSQL)."
)

MSG_DATABASE_URL_SQLITE = (
    "CONFIGURACAO INVALIDA: DATABASE_URL aponta para SQLite em PRODUCAO.\n"
    "Use a connectionString do PostgreSQL do Render. SQLite e permitido\n"
    "apenas no ambiente LOCAL/desenvolvimento."
)


class Config:
    """
    Classe de configuração do Flask.
    As configurações são acessadas via app.config.from_object().
    """

    # Ambiente detectado (local x produção) — evita comportamento ambíguo
    APP_ENV = (os.getenv("APP_ENV") or "development").strip().lower()
    EXECUTANDO_NO_RENDER = _booleano(os.getenv("RENDER"))
    PRODUCAO = (
        APP_ENV == "production"
        or EXECUTANDO_NO_RENDER
        or _booleano(os.getenv("PRODUCTION"))
    )

    # Chave secreta para assinar cookies, sessões e tokens CSRF
    # Em produção (Render) vem de variável de ambiente com generateValue.
    # O fallback existe apenas para desenvolvimento local.
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-key")

    # Cookies de sessão endurecidos (produção exige HTTPS no Render)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = PRODUCAO

    # Limite global de upload (fotos de profissionais: 2MB)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024

    # ============================================
    # BANCO DE DADOS
    # ============================================
    # LOCAL/DESENVOLVIMENTO: pode usar SQLite ("barbearia.db").
    # PRODUÇÃO: PostgreSQL via DATABASE_URL (obrigatório).
    #
    # Exemplos:
    #   LOCAL       sqlite:///caminho/para/barbearia.db
    #   PRODUÇÃO    postgresql://usuario:senha@host:5432/barbearia
    #
    # O banco é resolvido SEMPRE a partir de DATABASE_URL quando ela
    # existe: o PostgreSQL do Render nunca é substituído por SQLite.
    DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()

    if DATABASE_URL.startswith("sqlite") and PRODUCAO:
        # Proibido: SQLite em produção apagaria os dados no próximo restart
        raise RuntimeError(MSG_DATABASE_URL_SQLITE)

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
        BANCO_POSTGRES = DATABASE_URL.startswith("postgresql")
    elif PRODUCAO:
        # Falha explícita em vez de perder dados silenciosamente com SQLite
        raise RuntimeError(MSG_SEM_DATABASE_URL)
    else:
        # Fallback: SQLite local (APENAS desenvolvimento)
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "barbearia.db"
        )
        BANCO_POSTGRES = False

    # Desativa o rastreamento de modificações do SQLAlchemy (economiza memória)
    SQLALCHEMY_TRACK_MODIFICATIONS = False