# ============================================
# MODELO: Financeiro
# ============================================
# Representa o registro financeiro de um agendamento.
# Cada agendamento pode ter um registro financeiro associado.

from models import db
from datetime import datetime


class Financeiro(db.Model):
    """
    Tabela: financeiro
    Colunas:
        id                -> Identificador único (inteiro, chave primária)
        agendamento_id    -> ID do agendamento relacionado (inteiro, chave estrangeira)
        valor             -> Valor do serviço (inteiro, em reais)
        status            -> Status do pagamento (texto: pendente, pago, cancelado)
        forma_pagamento   -> Forma de pagamento (texto: dinheiro, cartao, pix)
        criado_em         -> Data/hora da criação do registro (automático)
    """

    __tablename__ = "financeiro"

    id = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(
        db.Integer,
        db.ForeignKey("agendamento.id"),
        nullable=False,
        unique=True  # Um agendamento só pode ter um registro financeiro
    )
    valor = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pendente")
    forma_pagamento = db.Column(db.String(20), nullable=True, default=None)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # ============================================
    # RELACIONAMENTO
    # ============================================
    # Cria um vínculo com o modelo Agendamento.
    # backref="financeiro": permite acessar o financeiro de um agendamento
    # via agendamento.financeiro
    agendamento = db.relationship("Agendamento", backref=db.backref("financeiro", uselist=False))

    def __repr__(self):
        return (
            f"<Financeiro {self.id}: Agendamento #{self.agendamento_id} - "
            f"R${self.valor} - {self.status}>"
        )