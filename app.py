# ============================================
# APLICAÇÃO PRINCIPAL
# ============================================
# Este arquivo cria e configura a aplicação Flask.
# Ele importa os modelos, registra os blueprints e inicia o servidor.

from flask import Flask, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from config import Config
from models import db
from models.servico import Servico
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
    app.run(debug=True)