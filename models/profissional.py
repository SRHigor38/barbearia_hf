# ============================================
# MODELO: Profissional (Barbeiro)
# ============================================
# Representa um barbeiro/profissional da HF Barbearia.
# Campos simplificados: foto, nome e status (ativo/inativo).

from models import db
from datetime import datetime


class Profissional(db.Model):
    """
    Tabela: profissional
    Colunas:
        id          -> Identificador único (inteiro, chave primária)
        nome        -> Nome do profissional
        foto        -> Caminho da foto (se vazio, usa imagem padrão)
        ativo       -> Se o profissional está ativo (True/False)
        criado_em   -> Data de criação
    """

    __tablename__ = "profissional"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    foto = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Profissional {self.id}: {self.nome}>"