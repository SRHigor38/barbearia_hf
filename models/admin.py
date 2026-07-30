# ============================================
# MODELO: Admin
# ============================================
# Representa um administrador do sistema.
# A senha é armazenada como hash (bcrypt), nunca em texto puro.

from models import db


class Admin(db.Model):
    """
    Tabela: admin
    Colunas:
        id            -> Identificador único (inteiro, chave primária)
        usuario       -> Nome de usuário para login (texto, único)
        senha_hash    -> Hash da senha gerado pelo bcrypt (texto)
    """

    __tablename__ = "admin"

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Admin {self.id}: {self.usuario}>"