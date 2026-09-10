# ============================================
# MODELO: PlanoBeneficio
# ============================================
# Representa os benefícios reais de um plano para um cliente específico.
# Criado a partir do PlanoTipoBeneficio quando o plano é ativado.
# Cada benefício tem sua própria quantidade e quantidade_utilizada.

from models import db


class PlanoBeneficio(db.Model):
    """
    Tabela: plano_beneficio
    Colunas:
        id                  -> Identificador único (chave primária)
        plano_id            -> FK para plano.id
        servico_id          -> FK para servico.id
        quantidade          -> Quantidade total (0 se ilimitado)
        quantidade_utilizada -> Quantidade já utilizada
        ilimitado           -> Se True, o serviço pode ser usado infinitamente
    """

    __tablename__ = "plano_beneficio"

    id = db.Column(db.Integer, primary_key=True)
    plano_id = db.Column(
        db.Integer,
        db.ForeignKey("plano.id"),
        nullable=False
    )
    servico_id = db.Column(
        db.Integer,
        db.ForeignKey("servico.id"),
        nullable=False
    )
    quantidade = db.Column(db.Integer, nullable=False, default=0)
    quantidade_utilizada = db.Column(db.Integer, nullable=False, default=0)
    ilimitado = db.Column(db.Boolean, nullable=False, default=False)

    # Relacionamento com Servico
    servico = db.relationship("Servico", backref="plano_beneficios")

    def __repr__(self):
        if self.ilimitado:
            return f"<PlanoBeneficio: {self.servico.nome} = Ilimitado>"
        return f"<PlanoBeneficio: {self.servico.nome} = {self.quantidade_utilizada}/{self.quantidade}>"

    @property
    def restante(self):
        """Retorna a quantidade restante. Para ilimitado, retorna None (representa infinito)."""
        if self.ilimitado:
            return None
        return max(0, self.quantidade - self.quantidade_utilizada)

    @property
    def disponivel(self):
        """Retorna True se o benefício ainda pode ser utilizado."""
        if self.ilimitado:
            return True
        return self.quantidade_utilizada < self.quantidade
