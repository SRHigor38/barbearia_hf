# ============================================
# MODELO: Bloqueio de Horário
# ============================================
# Representa um bloqueio manual de horário feito pelo administrador.
# Exemplo: cliente ligou por telefone e reservou o horário.

from models import db
from datetime import datetime


class Bloqueio(db.Model):
    """
    Tabela: bloqueio
    Colunas:
        id          -> Identificador único (inteiro, chave primária)
        data        -> Data do bloqueio (YYYY-MM-DD)
        horario     -> Horário bloqueado (HH:MM)
        motivo      -> Motivo do bloqueio (opcional)
        criado_em   -> Data de criação
    """

    __tablename__ = "bloqueio"

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10), nullable=False)
    horario = db.Column(db.String(5), nullable=False)
    motivo = db.Column(db.String(200), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Bloqueio {self.id}: {self.data} às {self.horario}>"