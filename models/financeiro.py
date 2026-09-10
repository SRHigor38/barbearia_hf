# ============================================
# MODELO: Financeiro
# ============================================
# Representa o registro financeiro de uma movimentação da barbearia.
# Evoluído para cobrir:
#   - Receitas de agendamentos normais (agendamento_id)
#   - Receitas de planos (venda/renovação) (plano_id)
#   - Taxas de cartão/maquininha vinculadas ao pagamento
# O valor é armazenado em REAIS (ex: 50.0 = R$ 50,00).
# Apenas registros com status == "pago" entram no faturamento.

from models import db
from datetime import datetime


class Financeiro(db.Model):
    """
    Tabela: financeiro
    Colunas:
        id                -> Identificador único (chave primária)
        agendamento_id    -> FK para agendamento.id (opcional — receita de serviço)
        plano_id          -> FK para plano.id (opcional — receita de plano/renovação)
        tipo              -> Origem: agendamento | plano | renovacao_plano
        descricao         -> Descrição da movimentação (ex: "Corte - João")
        valor             -> Valor em reais (Float; centavos suportados)
        taxa_cartao       -> Taxa da maquininha em reais (0 se não cartão)
        status            -> pendente | pago | cancelado (só "pago" entra no lucro)
        forma_pagamento   -> dinheiro | pix | cartao | None
        data_pagamento    -> Data do evento (YYYY-MM-DD) para filtros por período
        criado_em         -> Data/hora da criação do registro
    """

    __tablename__ = "financeiro"

    id = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(
        db.Integer,
        db.ForeignKey("agendamento.id"),
        nullable=True,
        unique=True  # Um agendamento só pode ter um registro financeiro
    )
    plano_id = db.Column(
        db.Integer,
        db.ForeignKey("plano.id"),
        nullable=True
    )
    tipo = db.Column(db.String(30), nullable=False, default="agendamento")
    descricao = db.Column(db.String(300), nullable=True)
    valor = db.Column(db.Float, nullable=False, default=0)
    taxa_cartao = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="pendente")
    forma_pagamento = db.Column(db.String(20), nullable=True, default=None)
    data_pagamento = db.Column(db.String(10), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # ============================================
    # RELACIONAMENTOS
    # ============================================
    agendamento = db.relationship(
        "Agendamento", backref=db.backref("financeiro", uselist=False)
    )
    plano = db.relationship("Plano", backref="financeiros")

    def __repr__(self):
        tipo = self.tipo or "agendamento"
        return (
            f"<Financeiro {self.id}: {tipo} - "
            f"R${self.valor:.2f} - {self.status}>"
        )