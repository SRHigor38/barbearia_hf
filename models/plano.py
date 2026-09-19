# ============================================
# MODELO: Plano (Plano Mensal)
# ============================================
# Representa um plano mensal de cortes da HF Barbearia.
# Cada plano pertence a um cliente e pode ter dias da semana
# permitidos, validade de 30 dias e benefícios por serviço.
#
# Convenção de dias:
#   1 = Segunda-feira
#   2 = Terça-feira
#   3 = Quarta-feira
#   4 = Quinta-feira
#   5 = Sexta-feira
#   6 = Sábado
#   7 = Domingo

from models import db
from datetime import datetime


class Plano(db.Model):
    """
    Tabela: plano
    Colunas:
        id                 -> Identificador único (inteiro, chave primária)
        cliente_id         -> FK para cliente.id (um cliente pode ter um plano)
        plano_tipo_id      -> FK para plano_tipo.id (tipo do plano: Bronze, Prata, etc.)
        nome               -> Nome do plano (ex: "Bronze")
        preco              -> Preço do plano em reais
        data_inicio        -> Data de início (YYYY-MM-DD)
        data_validade      -> Data de validade (YYYY-MM-DD, ativação + 30 dias)
        status             -> ATIVO / EXPIRADO / ESGOTADO / CANCELADO
        dias_permitidos    -> Dias da semana permitidos (ex: "1,2,3,4" = Seg..Qui)
        codigo_acesso      -> Código de acesso exclusivo para o cliente
        criado_em          -> Data de criação do registro
    """

    __tablename__ = "plano"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer, db.ForeignKey("cliente.id"), nullable=False, unique=True
    )
    plano_tipo_id = db.Column(
        db.Integer, db.ForeignKey("plano_tipo.id"), nullable=False
    )
    nome = db.Column(db.String(100), nullable=False)
    # preco em REAIS (Float) — preserva centavos (ex: 109.99)
    preco = db.Column(db.Float, nullable=False, default=0.0)
    data_inicio = db.Column(db.String(10), nullable=False)
    data_validade = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ATIVO")
    dias_permitidos = db.Column(db.String(30), nullable=False, default="1,2,3,4,5,6,7")
    codigo_acesso = db.Column(db.String(20), nullable=False, unique=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento: um plano pertence a um cliente
    cliente = db.relationship("Cliente", backref="plano")

    # Relacionamento: um plano pertence a um tipo de plano
    plano_tipo = db.relationship("PlanoTipo", backref="planos")

    # Relacionamento: um plano possui vários benefícios
    beneficios = db.relationship(
        "PlanoBeneficio",
        backref="plano",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return (
            f"<Plano {self.id}: Cliente {self.cliente_id} - "
            f"{self.nome} - {self.status}>"
        )

    @property
    def dias_permitidos_lista(self):
        """Retorna a lista de dias da semana permitidos como inteiros."""
        if not self.dias_permitidos:
            return []
        return [int(d) for d in self.dias_permitidos.split(",") if d.strip() != ""]

    @property
    def servicos_inclusos(self):
        """Lista de serviços incluídos neste plano (via plano_tipo)."""
        if self.plano_tipo:
            return self.plano_tipo.servicos_inclusos
        return []

    @property
    def duracao_total(self):
        """Duração total do pacote em minutos."""
        if self.plano_tipo:
            return self.plano_tipo.duracao_total
        return 0

    @property
    def tem_beneficio_ilimitado(self):
        """Retorna True se o plano possui pelo menos um benefício ilimitado."""
        return any(b.ilimitado for b in self.beneficios)

    def get_beneficio(self, servico_id):
        """Retorna o PlanoBeneficio para um serviço específico, ou None."""
        for b in self.beneficios:
            if b.servico_id == servico_id:
                return b
        return None

    def beneficios_disponiveis(self, servico_ids):
        """
        Verifica se todos os serviços solicitados têm benefícios disponíveis.
        Retorna (True, None) se todos disponíveis, ou (False, mensagem_erro).
        """
        for sid in servico_ids:
            beneficio = self.get_beneficio(sid)
            if beneficio is None:
                return False, "Seu plano não inclui este serviço."
            if not beneficio.disponivel:
                return False, f"Seu plano não possui mais benefícios de {beneficio.servico.nome}."
        return True, None
