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
from models.profissional import Profissional
from models.cliente import Cliente
from models.bloqueio import Bloqueio


# ============================================
# FUNÇÕES RELACIONADAS A SERVIÇOS
# ============================================


def listar_servicos_do_banco():
    """
    Busca todos os serviços cadastrados no banco de dados
    e retorna no formato de dicionário compatível com os templates.

    Formato de retorno:
    {
        "Corte": {"preco": 40, "tempo": 40, "descricao": "...", "categoria": "...", "badge": "...", "imagem": "..."},
        ...
    }
    """
    servicos_banco = Servico.query.all()
    servicos_dict = {}

    for servico in servicos_banco:
        servicos_dict[servico.nome] = {
            "preco": servico.preco,
            "tempo": servico.tempo,
            "descricao": servico.descricao,
            "categoria": servico.categoria,
            "badge": servico.badge,
            "imagem": servico.imagem,
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


def criar_agendamento(nome, telefone, data, horario, servico,
                      profissional_id=None, cliente_id=None, observacoes=None):
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
        servico=servico,
        profissional_id=profissional_id,
        cliente_id=cliente_id,
        observacoes=observacoes
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
# FUNÇÕES DE RELATÓRIOS
# ============================================


def listar_agendamentos_por_periodo(data_inicio, data_fim):
    """
    Busca agendamentos entre duas datas (inclusive).
    Retorna uma lista de objetos Agendamento ordenados por data.
    """
    return Agendamento.query.filter(
        Agendamento.data >= data_inicio,
        Agendamento.data <= data_fim
    ).order_by(Agendamento.data.asc(), Agendamento.horario.asc()).all()


def calcular_totais_periodo(agendamentos):
    """
    Calcula totais de um período a partir de uma lista de agendamentos.
    Retorna um dicionário com:
        - quantidade: número de agendamentos
        - total_faturado: soma dos valores (via financeiro)
        - ticket_medio: total_faturado / quantidade
    """
    from models.financeiro import Financeiro

    quantidade = len(agendamentos)
    total_faturado = 0

    for ag in agendamentos:
        financeiro = Financeiro.query.filter_by(agendamento_id=ag.id).first()
        if financeiro and financeiro.status == "pago":
            total_faturado += financeiro.valor

    ticket_medio = round(total_faturado / quantidade, 2) if quantidade > 0 else 0

    return {
        "quantidade": quantidade,
        "total_faturado": total_faturado,
        "ticket_medio": ticket_medio,
    }


# ============================================
# FUNÇÕES RELACIONADAS A PROFISSIONAIS
# ============================================


def listar_profissionais():
    """
    Retorna todos os profissionais ativos do banco.
    """
    return Profissional.query.filter_by(ativo=True).all()


def listar_todos_profissionais():
    """
    Retorna todos os profissionais (ativos e inativos).
    """
    return Profissional.query.all()


def buscar_profissional_por_id(profissional_id):
    """
    Busca um profissional pelo ID.
    Retorna o objeto Profissional ou None.
    """
    return Profissional.query.get(profissional_id)


def buscar_profissional_por_nome(nome):
    """
    Busca um profissional pelo nome (case-insensitive).
    Retorna o objeto Profissional ou None.
    """
    return Profissional.query.filter(
        db.func.lower(Profissional.nome) == nome.lower()
    ).first()


def criar_profissional(nome, especialidade, telefone, descricao, foto, tempo_medio):
    """
    Cria e salva um novo profissional no banco.
    """
    profissional = Profissional(
        nome=nome,
        especialidade=especialidade,
        telefone=telefone,
        descricao=descricao,
        foto=foto,
        tempo_medio=tempo_medio,
        ativo=True
    )
    db.session.add(profissional)
    db.session.commit()
    return profissional


def atualizar_profissional(profissional_id, nome=None, especialidade=None,
                           telefone=None, descricao=None, foto=None,
                           tempo_medio=None, ativo=None):
    """
    Atualiza os dados de um profissional existente.
    Retorna o objeto atualizado ou None se não existir.
    """
    profissional = buscar_profissional_por_id(profissional_id)
    if profissional is None:
        return None

    if nome is not None:
        profissional.nome = nome
    if especialidade is not None:
        profissional.especialidade = especialidade
    if telefone is not None:
        profissional.telefone = telefone
    if descricao is not None:
        profissional.descricao = descricao
    if foto is not None:
        profissional.foto = foto
    if tempo_medio is not None:
        profissional.tempo_medio = tempo_medio
    if ativo is not None:
        profissional.ativo = ativo

    db.session.commit()
    return profissional


def excluir_profissional(profissional_id):
    """
    Exclui um profissional somente se não possuir agendamentos.
    Retorna True se excluído, False se não for seguro excluir.
    """
    profissional = buscar_profissional_por_id(profissional_id)
    if profissional is None:
        return False

    # Verifica se o profissional possui agendamentos
    tem_agendamentos = Agendamento.query.filter_by(profissional_id=profissional_id).first()
    if tem_agendamentos:
        return False  # Não é seguro excluir — possui histórico

    db.session.delete(profissional)
    db.session.commit()
    return True


def contar_agendamentos_profissional(profissional_id):
    """
    Retorna a quantidade de agendamentos de um profissional.
    """
    return Agendamento.query.filter_by(profissional_id=profissional_id).count()


# ============================================
# FUNÇÕES DE DISPONIBILIDADE INDIVIDUAL
# ============================================


def verificar_conflito_profissional(profissional_id, data, horario_inicio, duracao_minutos):
    """
    Verifica se um profissional já possui agendamento que conflita
    com o intervalo [horario_inicio, horario_inicio + duracao].

    Considera sobreposição real de horários:
    - Se o novo agendamento começa antes do existente e termina depois
    - Se começa dentro do intervalo do existente
    - Se o existente começa dentro do intervalo do novo

    Retorna True se houver conflito, False caso contrário.
    """
    if not profissional_id:
        return False

    # Converte horário de início para minutos desde 00:00
    def para_minutos(hhmm):
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    inicio_novo = para_minutos(horario_inicio)
    fim_novo = inicio_novo + duracao_minutos

    # Busca todos os agendamentos do profissional na data
    agendamentos = Agendamento.query.filter_by(
        data=data,
        profissional_id=profissional_id
    ).all()

    for ag in agendamentos:
        # Busca a duração do serviço do agendamento existente
        servico_obj = Servico.query.filter_by(nome=ag.servico).first()
        duracao_existente = servico_obj.tempo if servico_obj else 40

        inicio_existente = para_minutos(ag.horario)
        fim_existente = inicio_existente + duracao_existente

        # Verifica sobreposição real
        if inicio_novo < fim_existente and inicio_existente < fim_novo:
            return True

    return False


def listar_horarios_disponiveis(profissional_id, data, duracao_servico):
    """
    Retorna a lista de horários disponíveis para um profissional em uma data,
    considerando a duração do serviço e os agendamentos existentes.

    Retorna uma lista de dicionários:
    [{"horario": "14:00", "disponivel": True, "ocupado": False, "bloqueado": False}, ...]
    """
    horarios_permitidos = [
        "08:00", "09:00", "10:00", "11:00",
        "13:00", "14:00", "15:00", "16:00", "17:00"
    ]

    resultado = []
    for horario in horarios_permitidos:
        ocupado = verificar_conflito_profissional(
            profissional_id, data, horario, duracao_servico
        )
        bloqueado = horario_esta_bloqueado(data, horario)

        resultado.append({
            "horario": horario,
            "disponivel": not ocupado and not bloqueado,
            "ocupado": ocupado,
            "bloqueado": bloqueado,
        })

    return resultado


# ============================================
# FUNÇÕES RELACIONADAS A CLIENTES
# ============================================


def listar_clientes():
    """
    Retorna todos os clientes cadastrados.
    """
    return Cliente.query.order_by(Cliente.nome.asc()).all()


def buscar_cliente_por_id(cliente_id):
    """
    Busca um cliente pelo ID.
    """
    return Cliente.query.get(cliente_id)


def buscar_cliente_por_telefone(telefone):
    """
    Busca um cliente pelo telefone.
    """
    return Cliente.query.filter_by(telefone=telefone).first()


def criar_cliente(nome, telefone, email=None, aniversario=None, observacoes=None):
    """
    Cria e salva um novo cliente no banco.
    Se já existir cliente com o mesmo telefone, retorna o existente.
    """
    cliente_existente = buscar_cliente_por_telefone(telefone)
    if cliente_existente:
        return cliente_existente

    cliente = Cliente(
        nome=nome,
        telefone=telefone,
        email=email,
        aniversario=aniversario,
        observacoes=observacoes
    )
    db.session.add(cliente)
    db.session.commit()
    return cliente


# ============================================
# FUNÇÕES RELACIONADAS A BLOQUEIOS
# ============================================


def listar_bloqueios_por_data(data):
    """
    Retorna todos os bloqueios de uma data específica.
    """
    return Bloqueio.query.filter_by(data=data).all()


def criar_bloqueio(data, horario, motivo=None):
    """
    Cria um bloqueio manual de horário.
    """
    bloqueio = Bloqueio(data=data, horario=horario, motivo=motivo)
    db.session.add(bloqueio)
    db.session.commit()
    return bloqueio


def remover_bloqueio(bloqueio_id):
    """
    Remove um bloqueio pelo ID.
    """
    bloqueio = Bloqueio.query.get(bloqueio_id)
    if bloqueio:
        db.session.delete(bloqueio)
        db.session.commit()
        return True
    return False


def horario_esta_bloqueado(data, horario):
    """
    Verifica se um horário está bloqueado manualmente.
    """
    return Bloqueio.query.filter_by(data=data, horario=horario).first() is not None


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

    # ============================================
    # CRIA PROFISSIONAL PADRÃO "HARRISON" (idempotente)
    # ============================================
    # Verifica se já existe um profissional chamado HARRISON
    # Se não existir, cria automaticamente como ativo.
    # Se já existir, NÃO cria outro (evita duplicidade).
    if buscar_profissional_por_nome("HARRISON") is None:
        harrison = Profissional(
            nome="HARRISON",
            especialidade="Cortes e Barba",
            telefone="",
            descricao="Profissional da HF Barbearia.",
            foto=None,
            tempo_medio=40,
            ativo=True
        )
        db.session.add(harrison)
        db.session.commit()
