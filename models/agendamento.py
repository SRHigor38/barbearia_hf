# ============================================
# MODELO: Agendamento
# ============================================
# Representa um agendamento feito por um cliente.
# Agora possui vínculo com profissional, cliente, plano e observações.
# Pode ter múltiplos serviços (via AgendamentoServico) quando feito com plano.

from models import db
from datetime import datetime


class Agendamento(db.Model):
    """
    Tabela: agendamento
    Colunas:
        id              -> Identificador único (inteiro, chave primária)
        nome            -> Nome do cliente (texto)
        telefone        -> Telefone do cliente (texto)
        data            -> Data do agendamento (texto no formato YYYY-MM-DD)
        horario         -> Horário do agendamento (texto, ex: "14:00")
        servico         -> Nome do serviço agendado (texto) — usado em agendamentos normais
        profissional_id -> ID do profissional (FK, opcional)
        cliente_id      -> ID do cliente (FK, opcional)
        plano_id        -> ID do plano (FK, opcional — quando feito com plano)
        observacoes     -> Observações do agendamento (opcional)
        criado_em       -> Data/hora em que o agendamento foi criado (automático)
    """

    __tablename__ = "agendamento"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    data = db.Column(db.String(10), nullable=False)
    horario = db.Column(db.String(5), nullable=False)
    servico = db.Column(db.String(100), nullable=False)
    profissional_id = db.Column(db.Integer, db.ForeignKey("profissional.id"), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=True)
    plano_id = db.Column(db.Integer, db.ForeignKey("plano.id"), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    profissional = db.relationship("Profissional", backref="agendamentos")
    cliente = db.relationship("Cliente", backref="agendamentos")
    plano = db.relationship("Plano", backref="agendamentos")

    # Relacionamento: um agendamento pode ter vários serviços (via tabela junction)
    servicos_relacionados = db.relationship(
        "AgendamentoServico",
        backref="agendamento",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return (
            f"<Agendamento {self.id}: {self.nome} - "
            f"{self.data} às {self.horario} - {self.servico}>"
        )

    @property
    def servicos_lista(self):
        """
        Retorna a lista de objetos Servico associados a este agendamento.
        - Se for um agendamento de plano (plano_id definido), retorna os serviços
          da tabela AgendamentoServico.
        - Se for um agendamento normal, retorna uma lista com o único serviço
          referenciado pelo campo `servico`.
        """
        if self.plano_id and self.servicos_relacionados:
            return [asr.servico for asr in self.servicos_relacionados if asr.servico]
        # Agendamento normal: busca o serviço pelo nome
        from models.servico import Servico
        servico_obj = Servico.query.filter_by(nome=self.servico).first()
        if servico_obj:
            return [servico_obj]
        return []

    @property
    def duracao_total(self):
        """Duração total do agendamento em minutos (soma de todos os serviços)."""
        return sum(s.tempo for s in self.servicos_lista)
