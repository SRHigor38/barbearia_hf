# ============================================
# APLICAÇÃO PRINCIPAL
# ============================================
# Este arquivo cria e configura a aplicação Flask.
# Ele importa os modelos, registra os blueprints e inicia o servidor.

import os
import sys

# Faz o console aceitar caracteres UTF-8 (ex: emojis em prints)
# Essencial no Windows (cp1252) e seguro em Linux/produção.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from flask import Flask, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from config import Config
from models import db
from services.financeiro_service import formatar_moeda, aplicar_migracoes
from utils import formatar_telefone
from models.admin import Admin
from routes import main_bp, admin_bp
from services.barbearia_service import criar_banco_e_popular


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

    # Inicializa o banco de dados com a aplicação
    db.init_app(app)

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
        """Erro 500: Erro interno do servidor."""
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
    with app.app_context():
        # Cria as tabelas e insere serviços iniciais
        criar_banco_e_popular()

        # Aplica migrações seguras (adiciona colunas novas sem apagar dados)
        aplicar_migracoes()

        # Cria admin padrão se não existir
        if Admin.query.first() is None:
            # Senha inicial configurável por ambiente (ADMIN_SENHA_INICIAL).
            # Fallback "admin123" apenas para desenvolvimento local —
            # EM PRODUÇÃO defina ADMIN_SENHA_INICIAL e/ou troque a senha
            # em /admin/config após o primeiro login.
            senha_inicial = os.getenv("ADMIN_SENHA_INICIAL", "admin123")
            admin = Admin(
                usuario="admin",
                senha_hash=bcrypt.generate_password_hash(senha_inicial).decode("utf-8")
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin padrao criado: usuario=admin (defina ADMIN_SENHA_INICIAL em producao)")

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
