# ============================================
# MODELO: Cliente
# ============================================
# Representa um cliente da HF Barbearia.
# Possui histórico de agendamentos e dados de contato.

from models import db
from datetime import datetime


class Cliente(db.Model):
    """
    Tabela: cliente
    Colunas:
        id             -> Identificador único (inteiro, chave primária)
        nome           -> Nome do cliente
        telefone       -> Telefone de contato (unique)
        email          -> E-mail (opcional)
        aniversario    -> Data de nascimento (opcional)
        observacoes    -> Notas do barbeiro sobre o cliente
        criado_em      -> Data de criação
    """

    __tablename__ = "cliente"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    aniversario = db.Column(db.String(10), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Cliente {self.id}: {self.nome} - {self.telefone}>"