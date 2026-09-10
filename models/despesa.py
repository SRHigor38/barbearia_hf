# ============================================
# MODELO: Despesa (Gastos da Barbearia)
# ============================================
# Representa um gasto manual da barbearia (produtos, aluguel,
# energia, água, internet, etc.) e também pode representar
# taxas de maquininha quando vinculadas a um agendamento.
# O valor é armazenado em REAIS (Float, centavos suportados).

from models import db
from datetime import datetime


class Despesa(db.Model):
    """
    Tabela: despesa
    Colunas:
        id            -> Identificador único (chave primária)
        descricao     -> Descrição do gasto (obrigatória)
        categoria     -> Categoria (Produtos, Aluguel, Energia, etc.)
        valor         -> Valor em reais (Float; deve ser > 0)
        data          -> Data do gasto (YYYY-MM-DD)
        observacao    -> Observação opcional
        criado_em     -> Data/hora de criação do registro
    """

    __tablename__ = "despesa"

    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(50), nullable=False, default="Outros")
    valor = db.Column(db.Float, nullable=False, default=0)
    data = db.Column(db.String(10), nullable=False)
    observacao = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Despesa {self.id}: {self.descricao} - R${self.valor:.2f}>"