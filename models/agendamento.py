# ============================================
# MODELO: Agendamento
# ============================================
# Representa um agendamento feito por um cliente.

from models import db
from datetime import datetime


class Agendamento(db.Model):
    """
    Tabela: agendamento
    Colunas:
        id         -> Identificador único (inteiro, chave primária)
        nome       -> Nome do cliente (texto)
        telefone   -> Telefone do cliente (texto)
        data       -> Data do agendamento (texto no formato YYYY-MM-DD)
        horario    -> Horário do agendamento (texto, ex: "14:00")
        servico    -> Nome do serviço agendado (texto)
        criado_em  -> Data/hora em que o agendamento foi criado (automático)
    """

    __tablename__ = "agendamento"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    data = db.Column(db.String(10), nullable=False)
    horario = db.Column(db.String(5), nullable=False)
    servico = db.Column(db.String(100), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<Agendamento {self.id}: {self.nome} - "
            f"{self.data} às {self.horario} - {self.servico}>"
        )