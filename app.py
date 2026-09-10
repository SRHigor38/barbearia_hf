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
from models.servico import Servico
from models.admin import Admin
from models.profissional import Profissional
from models.cliente import Cliente
from models.bloqueio import Bloqueio
from models.plano import Plano
from models.plano_tipo import PlanoTipo
from models.plano_tipo_beneficio import PlanoTipoBeneficio
from models.plano_beneficio import PlanoBeneficio
from models.agendamento_servico import AgendamentoServico
from models.financeiro import Financeiro
from models.despesa import Despesa
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
            admin = Admin(
                usuario="admin",
                senha_hash=bcrypt.generate_password_hash("admin123").decode("utf-8")
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin padrão criado: usuario=admin / senha=admin123")

    return app


# ============================================
# PONTO DE ENTRADA
# ============================================
# Se este arquivo for executado diretamente, cria a app e inicia o servidor.
if __name__ == "__main__":
    app = create_app()
    # debug=True apenas em desenvolvimento
    # Para produção, defina FLASK_DEBUG=false no .env
    debug_mode = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug_mode)
