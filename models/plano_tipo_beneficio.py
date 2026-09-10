# ============================================
# MODELO: PlanoTipoBeneficio
# ============================================
# Define quais serviços e benefícios cada plano tipo inclui.
# Esta é a definição do catálogo — não muda por cliente.
# Exemplo: Bronze inclui Corte (4) e Barba (4)

from models import db


class PlanoTipoBeneficio(db.Model):
    """
    Tabela: plano_tipo_beneficio
    Colunas:
        id           -> Identificador único (chave primária)
        plano_tipo_id -> FK para plano_tipo.id
        servico_id   -> FK para servico.id
        quantidade   -> Quantidade total de vezes que o serviço pode ser usado
        ilimitado    -> Se True, o serviço pode ser usado infinitamente
    """

    __tablename__ = "plano_tipo_beneficio"

    id = db.Column(db.Integer, primary_key=True)
    plano_tipo_id = db.Column(
        db.Integer,
        db.ForeignKey("plano_tipo.id"),
        nullable=False
    )
    servico_id = db.Column(
        db.Integer,
        db.ForeignKey("servico.id"),
        nullable=False
    )
    quantidade = db.Column(db.Integer, nullable=False, default=0)
    ilimitado = db.Column(db.Boolean, nullable=False, default=False)

    # Relacionamento com Servico
    servico = db.relationship("Servico", backref="plano_tipo_beneficios")

    def __repr__(self):
        if self.ilimitado:
            return f"<PlanoTipoBeneficio: {self.servico.nome} = Ilimitado>"
        return f"<PlanoTipoBeneficio: {self.servico.nome} = {self.quantidade}>"
