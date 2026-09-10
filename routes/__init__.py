# ============================================
# REGISTRO DE BLUEPRINTS
# ============================================
# Blueprints são módulos que agrupam rotas relacionadas.
# Cada blueprint pode ter seu próprio prefixo de URL.

from flask import Blueprint

# Blueprint para rotas públicas (/, /agendamento)
main_bp = Blueprint("main", __name__)

# Blueprint para rotas administrativas.
# Usa um prefixo separado e não divulgado na interface pública.
# O acesso administrativo NÃO aparece no menu público.
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Importa as rotas de cada blueprint para registrá-las
from routes import main  # noqa: E402, F401
from routes import admin  # noqa: E402, F401