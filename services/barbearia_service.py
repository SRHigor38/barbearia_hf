# ============================================
# SERVIÇO: Lógica de Negócio
# ============================================
# Contém funções auxiliares usadas pelas rotas.
# Separa a lógica de negócio do controle (rotas).

import re
from datetime import datetime
from models import db
from models.servico import Servico
from models.agendamento import Agendamento
from models.financeiro import Financeiro


# ============================================
# FUNÇÕES RELACIONADAS A SERVIÇOS
# ============================================


def listar_servicos_do_banco():
    """
    Busca todos os serviços cadastrados no banco de dados
    e retorna no formato de dicionário compatível com os templates.

    Formato de retorno:
    {
        "Corte": {"preco": 40, "tempo": 40},
        "Barba": {"preco": 25, "tempo": 25},
        ...
    }
    """
    servicos_banco = Servico.query.all()
    servicos_dict = {}

    for servico in servicos_banco:
        servicos_dict[servico.nome] = {
            "preco": servico.preco,
            "tempo": servico.tempo,
        }

    return servicos_dict


def servico_existe_no_banco(nome_servico):
    """
    Verifica se um serviço existe no banco de dados pelo nome.
    Retorna True se existe, False caso contrário.
    """
    servico = Servico.query.filter_by(nome=nome_servico).first()
    return servico is not None


def buscar_servico_por_nome(nome_servico):
    """
    Busca um serviço no banco pelo nome.
    Retorna o objeto Servico ou None se não existir.
    """
    return Servico.query.filter_by(nome=nome_servico).first()


def contar_servicos():
    """
    Retorna a quantidade total de serviços cadastrados no banco.
    """
    return Servico.query.count()


# ============================================
# FUNÇÕES DE VALIDAÇÃO
# ============================================


def validar_telefone(telefone):
    """
    Valida o formato do telefone usando expressão regular.
    Formatos aceitos: (11) 99999-8888, 11999998888, 113333-4444
    Retorna True se válido, False caso contrário.
    """
    padrao = r"^\(?\d{2}\)?\s?\d{4,5}-?\d{4}$"
    return re.match(padrao, telefone.strip()) is not None


def validar_data(data_str):
    """
    Valida se a data está no formato YYYY-MM-DD e é futura.
    Retorna (True, objeto_data) se válida.
    Retorna (False, mensagem_erro) se inválida.
    """
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return False, "Data inválida. Use o formato DD/MM/AAAA."

    hoje = datetime.now().date()

    if data_obj < hoje:
        return False, "A data deve ser hoje ou uma data futura."

    return True, data_obj


def validar_horario(horario):
    """
    Verifica se o horário está na lista de horários permitidos.
    Retorna True se válido, False caso contrário.
    """
    horarios_permitidos = [
        "08:00", "09:00", "10:00", "11:00",
        "13:00", "14:00", "15:00", "16:00", "17:00"
    ]
    return horario in horarios_permitidos


# ============================================
# FUNÇÕES RELACIONADAS A AGENDAMENTOS
# ============================================


def verificar_conflito_horario(data, horario):
    """
    Verifica se já existe um agendamento para a mesma data e horário.
    Retorna True se houver conflito, False caso contrário.
    """
    conflito = Agendamento.query.filter_by(
        data=data,
        horario=horario
    ).first()
    return conflito is not None


def criar_agendamento(nome, telefone, data, horario, servico):
    """
    Cria e salva um novo agendamento no banco de dados.
    Também cria automaticamente o registro financeiro associado.
    Retorna o objeto Agendamento criado.
    """

    # Cria o agendamento
    novo_agendamento = Agendamento(
        nome=nome.strip(),
        telefone=telefone.strip(),
        data=data,
        horario=horario,
        servico=servico
    )
    db.session.add(novo_agendamento)
    db.session.flush()  # Força o ID a ser gerado sem commit

    # Busca o preço do serviço para criar o registro financeiro
    servico_obj = Servico.query.filter_by(nome=servico).first()
    valor = servico_obj.preco if servico_obj else 0

    # Cria o registro financeiro automaticamente
    financeiro = Financeiro(
        agendamento_id=novo_agendamento.id,
        valor=valor,
        status="pendente"  # Pendente até o admin confirmar o pagamento
    )
    db.session.add(financeiro)

    # Salva tudo no banco
    db.session.commit()
    return novo_agendamento


# ============================================
# FUNÇÕES DE INICIALIZAÇÃO
# ============================================


def criar_banco_e_popular():
    """
    Cria as tabelas no banco de dados e insere os serviços
    iniciais (caso ainda não existam).
    """
    db.create_all()

    if Servico.query.first() is None:
        servicos_iniciais = [
            {"nome": "Corte", "preco": 40, "tempo": 40},
            {"nome": "Barba", "preco": 25, "tempo": 25},
            {"nome": "Limpeza", "preco": 30, "tempo": 30},
            {"nome": "Sobrancelha", "preco": 20, "tempo": 20},
            {"nome": "Combo Premium", "preco": 80, "tempo": 90},
        ]

        for dados in servicos_iniciais:
            servico = Servico(
                nome=dados["nome"],
                preco=dados["preco"],
                tempo=dados["tempo"],
            )
            db.session.add(servico)

        db.session.commit()