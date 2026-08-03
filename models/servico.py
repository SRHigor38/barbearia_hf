# ============================================
# MODELO: Servico
# ============================================
# Representa um serviço oferecido pela barbearia.

from models import db


class Servico(db.Model):
    """
    Tabela: servico
    Colunas:
        id        -> Identificador único (inteiro, chave primária)
        nome      -> Nome do serviço (texto, ex: "Corte")
        preco     -> Preço em reais (inteiro, ex: 40)
        tempo     -> Duração em minutos (inteiro, ex: 40)
    """

    __tablename__ = "servico"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    preco = db.Column(db.Integer, nullable=False)
    tempo = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f"<Servico {self.id}: {self.nome} - R${self.preco} - {self.tempo}min>"