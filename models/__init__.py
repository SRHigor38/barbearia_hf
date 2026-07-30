# ============================================
# INICIALIZAÇÃO DO BANCO DE DADOS
# ============================================
# Este arquivo torna a pasta 'models' um pacote Python.
# O objeto 'db' é criado aqui e importado pelos modelos
# e pelo app.py, evitando importação circular.

from flask_sqlalchemy import SQLAlchemy

# Cria o objeto do banco de dados (sem associar a app ainda)
db = SQLAlchemy()