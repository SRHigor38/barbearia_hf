# ============================================
# MODELO: Profissional (Barbeiro)
# ============================================
# Representa um barbeiro/profissional da HF Barbearia.
# Cada profissional possui especialidade, foto e agenda própria.

from models import db
from datetime import datetime


class Profissional(db.Model):
    """
    Tabela: profissional
    Colunas:
        id             -> Identificador único (inteiro, chave primária)
        nome           -> Nome do profissional
        especialidade  -> Especialidade principal (ex: "Cortes", "Barba")
        telefone       -> Telefone de contato
        descricao      -> Breve descrição do profissional
        foto           -> Caminho da foto (se vazio, usa imagem padrão)
        tempo_medio    -> Tempo médio em minutos
        ativo          -> Se o profissional está ativo (bool)
        criado_em      -> Data de criação
    """

    __tablename__ = "profissional"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especialidade = db.Column(db.String(100), nullable=True)
    telefone = db.Column(db.String(20), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    foto = db.Column(db.String(255), nullable=True)
    tempo_medio = db.Column(db.Integer, nullable=True, default=40)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Profissional {self.id}: {self.nome} - {self.especialidade}>"