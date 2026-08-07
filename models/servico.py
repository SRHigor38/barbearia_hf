# ============================================
# MODELO: Servico
# ============================================
# Representa um serviço oferecido pela HF Barbearia.
# Agora possui descrição, categoria, badge (etiqueta) e imagem.

from models import db


class Servico(db.Model):
    """
    Tabela: servico
    Colunas:
        id          -> Identificador único (inteiro, chave primária)
        nome        -> Nome do serviço (texto, ex: "Corte")
        descricao   -> Descrição detalhada do serviço
        preco       -> Preço em reais (inteiro, ex: 40)
        tempo       -> Duração em minutos (inteiro, ex: 40)
        categoria   -> Categoria do serviço (ex: "Corte", "Barba", "Tratamento")
        badge       -> Etiqueta (ex: "Mais vendido", "Promoção") — opcional
        imagem      -> Caminho da imagem (se vazio, usa imagem padrão)
    """

    __tablename__ = "servico"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    preco = db.Column(db.Integer, nullable=False)
    tempo = db.Column(db.Integer, nullable=False)
    categoria = db.Column(db.String(100), nullable=True)
    badge = db.Column(db.String(50), nullable=True)
    imagem = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<Servico {self.id}: {self.nome} - R${self.preco} - {self.tempo}min>"