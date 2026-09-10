# ============================================
# MODELO: AgendamentoServico
# ============================================
# Tabela intermediária entre Agendamento e Servico.
# Permite que um único agendamento possua vários serviços
# (ex: Corte + Barba como um único atendimento).

from models import db


class AgendamentoServico(db.Model):
    """
    Tabela: agendamento_servico
    Colunas:
        id             -> Identificador único (chave primária)
        agendamento_id -> FK para agendamento.id
        servico_id     -> FK para servico.id
    """

    __tablename__ = "agendamento_servico"

    id = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(
        db.Integer,
        db.ForeignKey("agendamento.id"),
        nullable=False
    )
    servico_id = db.Column(
        db.Integer,
        db.ForeignKey("servico.id"),
        nullable=False
    )

    # Relacionamento com Servico
    servico = db.relationship("Servico", backref="agendamento_servicos")

    def __repr__(self):
        return f"<AgendamentoServico: Agendamento #{self.agendamento_id} - {self.servico.nome}>"
