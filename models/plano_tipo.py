# ============================================
# MODELO: PlanoTipo (Catálogo de Planos Pré-definidos)
# ============================================
# Representa os 8 planos pré-definidos da HF Barbearia.
# Cada plano tipo define quais serviços e benefícios inclui.
# Exemplos: Bronze, Prata, Ouro, VIP, Elite, Basic, Light, Premium

from models import db


class PlanoTipo(db.Model):
    """
    Tabela: plano_tipo
    Colunas:
        id          -> Identificador único (chave primária)
        nome        -> Nome do plano (ex: "Bronze", "Prata", "VIP")
        preco       -> Preço do plano em reais (inteiro)
        descricao   -> Descrição breve do plano
        dias_permitidos -> Dias da semana padrão (ex: "1,2,3,4")
    """

    __tablename__ = "plano_tipo"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)
    # preco em REAIS (Float) — preserva centavos (ex: 109.99)
    preco = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    dias_permitidos = db.Column(db.String(30), nullable=False, default="1,2,3,4")

    # Relacionamento: um plano tipo possui vários benefícios
    beneficios = db.relationship(
        "PlanoTipoBeneficio",
        backref="plano_tipo",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<PlanoTipo {self.id}: {self.nome} - R${self.preco}>"

    @property
    def servicos_inclusos(self):
        """Lista de serviços incluídos neste plano tipo."""
        return [b.servico for b in self.beneficios]

    @property
    def duracao_total(self):
        """Duração total do pacote em minutos (soma de todos os serviços)."""
        return sum(b.servico.tempo for b in self.beneficios if b.servico)
