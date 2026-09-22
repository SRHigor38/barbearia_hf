# ============================================
# APLICAÇÃO PRINCIPAL
# ============================================
# Este arquivo cria e configura a aplicação Flask.
# Ele importa os modelos, registra os blueprints e inicia o servidor.

import logging
import os
import sys

# Faz o console aceitar caracteres UTF-8 (ex: emojis em prints)
# Essencial no Windows (cp1252) e seguro em Linux/produção.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from flask import Flask, redirect, url_for, flash, request, has_request_context
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from config import Config, MSG_SEM_ADMIN_SENHA
from models import db
from services.financeiro_service import formatar_moeda, aplicar_migracoes
from utils import formatar_telefone
from models.admin import Admin
from routes import main_bp, admin_bp
from services.barbearia_service import criar_banco_e_popular


def registrar_banco_em_uso(app):
    """
    Escreve nos logs (Render) qual banco está REALMENTE em uso.

    Em produção deve aparecer sempre 'postgresql': se aparecer 'sqlite' no
    Render, o disco é efêmero e os dados (agendamentos, clientes, planos,
    financeiro) serão perdidos no próximo restart/sleep/redeploy.
    A senha da conexão nunca é exibida nos logs.
    """
    from sqlalchemy.engine.url import make_url

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    try:
        url = make_url(uri)
        dialeto = url.get_backend_name()
        destino = url.render_as_string(hide_password=True)
    except Exception:
        dialeto = "desconhecido"
        destino = "(url invalida)"

    app.logger.info(
        "BANCO EM USO: motor=%s | destino=%s | APP_ENV=%s | PRODUCAO=%s",
        dialeto,
        destino,
        app.config.get("APP_ENV"),
        app.config.get("PRODUCAO"),
    )

    if app.config.get("PRODUCAO") and dialeto != "postgresql":
        app.logger.error(
            "ATENCAO: producao deveria usar PostgreSQL, mas o motor atual e '%s'. "
            "Configure DATABASE_URL com a connectionString do PostgreSQL do Render.",
            dialeto,
        )


def create_app():
    """
    Função factory que cria e configura a aplicação Flask.
    Retorna a aplicação pronta para ser executada.
    """
    # Cria a aplicação Flask
    app = Flask(__name__)

    # Registra o filtro global de formatação de moeda para todos os templates
    app.jinja_env.filters["formatar_moeda"] = formatar_moeda

    # Registra o filtro global de formatação de telefone (padrão brasileiro)
    app.jinja_env.filters["formatar_telefone"] = formatar_telefone

    # Carrega as configurações da classe Config
    app.config.from_object(Config)

    # Garante que os diagnósticos (nível INFO) apareçam nos logs do Render
    app.logger.setLevel(logging.INFO)

    # Inicializa o banco de dados com a aplicação
    db.init_app(app)

    # Registra nos logs qual banco está em uso (diagnóstico de persistência)
    registrar_banco_em_uso(app)

    # Inicializa a proteção CSRF
    csrf = CSRFProtect(app)

    # Inicializa o bcrypt (para criptografia de senhas)
    # Armazena na configuração da app para ser acessível em outros módulos
    bcrypt = Bcrypt(app)
    app.bcrypt = bcrypt

    # ============================================
    # REGISTRO DOS BLUEPRINTS
    # ============================================
    # Blueprint main: rotas públicas (/, /agendamento)
    app.register_blueprint(main_bp)

    # Blueprint admin: rotas administrativas (/admin, /admin/login, etc.)
    app.register_blueprint(admin_bp)

    # ============================================
    # TRATAMENTO DE ERROS (ERROR HANDLERS)
    # ============================================
    @app.errorhandler(404)
    def pagina_nao_encontrada(erro):
        """Erro 404: Página não encontrada."""
        flash("Página não encontrada.", "warning")
        return redirect(url_for("main.inicio"))

    @app.errorhandler(500)
    def erro_interno(erro):
        """
        Erro 500: Erro interno do servidor.

        A mensagem exibida ao usuário continua genérica, mas a exceção REAL
        é registrada no log (aparece no Render > Logs), com traceback, para
        permitir o diagnóstico em produção.
        """
        excecao = getattr(erro, "original_exception", None)
        caminho = request.path if has_request_context() else "(sem requisicao)"
        app.logger.error(
            "Erro interno (HTTP 500) em %s: %s",
            caminho,
            excecao if excecao is not None else erro,
            exc_info=excecao if excecao is not None else True,
        )
        flash("Erro interno do servidor. Tente novamente.", "error")
        return redirect(url_for("main.inicio"))

    @app.errorhandler(400)
    def requisicao_invalida(erro):
        """Erro 400: Requisição inválida (inclui erros de CSRF)."""
        flash("Requisição inválida. Verifique os dados enviados.", "error")
        return redirect(url_for("main.inicio"))

    @app.errorhandler(413)
    def arquivo_muito_grande(erro):
        """Erro 413: upload acima de MAX_CONTENT_LENGTH (2MB)."""
        flash("Arquivo muito grande. Envie uma imagem de até 2MB.", "error")
        return redirect(url_for("admin.listar_profissionais"))

    # ============================================
    # CRIAÇÃO DO BANCO E DADOS INICIAIS
    # ============================================
    # 100% NÃO DESTRUTIVO: apenas cria tabelas que faltam e insere
    # registros padrão quando a tabela está vazia. Nenhum dado existente
    # é apagado ou recriado (não existe drop_all / drop table / delete em massa).
    with app.app_context():
        try:
            # Cria as tabelas e insere serviços iniciais
            criar_banco_e_popular()

            # Aplica migrações seguras (adiciona colunas novas sem apagar dados)
            aplicar_migracoes()

            # Cria admin padrão se não existir
            if Admin.query.first() is None:
                # Senha inicial configurável por ambiente (ADMIN_SENHA_INICIAL).
                # EM PRODUÇÃO ela é OBRIGATÓRIA: criar o admin com a senha
                # padrão "admin123" deixaria o painel aberto para qualquer
                # pessoa. O fallback continua valendo apenas no ambiente
                # LOCAL/desenvolvimento.
                senha_inicial = (os.getenv("ADMIN_SENHA_INICIAL") or "").strip()

                if not senha_inicial and Config.PRODUCAO:
                    # Fail-fast: o except abaixo faz rollback e interrompe a
                    # subida do serviço em vez de criar um admin inseguro.
                    raise RuntimeError(MSG_SEM_ADMIN_SENHA)

                if not senha_inicial:
                    # Fallback APENAS para desenvolvimento local
                    senha_inicial = "admin123"

                admin = Admin(
                    usuario="admin",
                    senha_hash=bcrypt.generate_password_hash(senha_inicial).decode("utf-8")
                )
                db.session.add(admin)
                db.session.commit()
                print("Admin padrao criado: usuario=admin (defina ADMIN_SENHA_INICIAL em producao)")
        except Exception:
            # Registra a causa REAL no log do Render e interrompe a subida
            # do serviço (fail-fast) em vez de subir com o banco incorreto.
            try:
                db.session.rollback()
            except Exception:
                pass
            app.logger.exception(
                "Falha ao inicializar a aplicacao (fail-fast proposital). "
                "Verifique DATABASE_URL, SECRET_KEY e ADMIN_SENHA_INICIAL."
            )
            raise

    return app


# ============================================
# INSTÂNCIA DA APLICAÇÃO (nível de módulo)
# ============================================
# O objeto `app` precisa existir no nível do módulo para que servidores
# WSGI (Gunicorn) e plataformas de deploy (Render/Heroku) importem a
# aplicação via "app:app" (ver Procfile e render.yaml).
app = create_app()


# ============================================
# PONTO DE ENTRADA
# ============================================
# Se este arquivo for executado diretamente, inicia o servidor de
# desenvolvimento. Em produção use Gunicorn (Procfile/render.yaml).
if __name__ == "__main__":
    # debug=True apenas em desenvolvimento
    # Para produção, defina FLASK_DEBUG=false no .env
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)
