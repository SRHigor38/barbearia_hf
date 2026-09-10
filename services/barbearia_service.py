# ============================================
# SERVIÇO: Lógica de Negócio
# ============================================
# Contém funções auxiliares usadas pelas rotas.
# Separa a lógica de negócio do controle (rotas).

import re
import secrets
import string
from datetime import datetime, timedelta
from models import db
from models.servico import Servico
from models.agendamento import Agendamento
from models.financeiro import Financeiro
from models.profissional import Profissional
from models.cliente import Cliente
from models.bloqueio import Bloqueio
from models.plano import Plano
from models.plano_tipo import PlanoTipo
from models.plano_tipo_beneficio import PlanoTipoBeneficio
from models.plano_beneficio import PlanoBeneficio
from models.agendamento_servico import AgendamentoServico


# ============================================
# CATÁLOGO DE PLANOS PRÉ-DEFINIDOS
# ============================================
# Preços em centavos (R$ 90,00 = 9000)
# Valores oficiais:
#   Bronze  = R$ 90,00
#   Prata   = R$ 80,00
#   Ouro    = R$ 95,00
#   VIP     = R$ 109,99
#   Elite   = R$ 79,99
#   Basic   = R$ 80,00
#   Light   = R$ 70,00
#   Premium = R$ 90,00

PLANOS_PREDEFINIDOS = [
    {
        "nome": "Bronze",
        "preco": 9000,
        "descricao": "4 Cortes + 4 Barbas por mês",
        "dias_permitidos": "1,2,3,4",
        "beneficios": [
            {"servico": "Corte", "quantidade": 4, "ilimitado": False},
            {"servico": "Barba", "quantidade": 4, "ilimitado": False},
        ],
    },
    {
        "nome": "Prata",
        "preco": 8000,
        "descricao": "4 Cortes + 4 Sobrancelhas por mês",
        "dias_permitidos": "1,2,3,4",
        "beneficios": [
            {"servico": "Corte", "quantidade": 4, "ilimitado": False},
            {"servico": "Sobrancelha", "quantidade": 4, "ilimitado": False},
        ],
    },
    {
        "nome": "Ouro",
        "preco": 9500,
        "descricao": "4 Cortes + 4 Barbas + 4 Sobrancelhas por mês",
        "dias_permitidos": "1,2,3,4",
        "beneficios": [
            {"servico": "Corte", "quantidade": 4, "ilimitado": False},
            {"servico": "Barba", "quantidade": 4, "ilimitado": False},
            {"servico": "Sobrancelha", "quantidade": 4, "ilimitado": False},
        ],
    },
    {
        "nome": "VIP",
        "preco": 10999,
        "descricao": "Corte, Barba e Sobrancelha ilimitados",
        "dias_permitidos": "1,2,3,4",
        "beneficios": [
            {"servico": "Corte", "quantidade": 0, "ilimitado": True},
            {"servico": "Barba", "quantidade": 0, "ilimitado": True},
            {"servico": "Sobrancelha", "quantidade": 0, "ilimitado": True},
        ],
    },
    {
        "nome": "Elite",
        "preco": 7999,
        "descricao": "Corte ilimitado",
        "dias_permitidos": "1,2,3",
        "beneficios": [
            {"servico": "Corte", "quantidade": 0, "ilimitado": True},
        ],
    },
    {
        "nome": "Basic",
        "preco": 8000,
        "descricao": "3 Cortes + 3 Barbas por mês",
        "dias_permitidos": "1,2,3,4",
        "beneficios": [
            {"servico": "Corte", "quantidade": 3, "ilimitado": False},
            {"servico": "Barba", "quantidade": 3, "ilimitado": False},
        ],
    },
    {
        "nome": "Light",
        "preco": 7000,
        "descricao": "3 Cortes por mês",
        "dias_permitidos": "1,2,3",
        "beneficios": [
            {"servico": "Corte", "quantidade": 3, "ilimitado": False},
        ],
    },
    {
        "nome": "Premium",
        "preco": 9000,
        "descricao": "3 Cortes + 3 Barbas + 3 Sobrancelhas por mês",
        "dias_permitidos": "1,2,3,4",
        "beneficios": [
            {"servico": "Corte", "quantidade": 3, "ilimitado": False},
            {"servico": "Barba", "quantidade": 3, "ilimitado": False},
            {"servico": "Sobrancelha", "quantidade": 3, "ilimitado": False},
        ],
    },
]


# ============================================
# FUNÇÕES RELACIONADAS A SERVIÇOS
# ============================================


def listar_servicos_do_banco():
    """
    Busca todos os serviços cadastrados no banco de dados
    e retorna no formato de dicionário compatível com os templates.
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
    """Verifica se um serviço existe no banco pelo nome."""
    return Servico.query.filter_by(nome=nome_servico).first() is not None


def buscar_servico_por_nome(nome_servico):
    """Busca um serviço no banco pelo nome. Retorna o objeto ou None."""
    return Servico.query.filter_by(nome=nome_servico).first()


def buscar_servico_por_id(servico_id):
    """Busca um serviço pelo ID."""
    return Servico.query.get(servico_id)


def contar_servicos():
    """Retorna a quantidade total de serviços cadastrados."""
    return Servico.query.count()


# ============================================
# FUNÇÕES DE VALIDAÇÃO
# ============================================


def validar_telefone(telefone):
    """Valida o formato do telefone. Retorna True se válido."""
    padrao = r"^\(?\d{2}\)?\s?\d{4,5}-?\d{4}$"
    return re.match(padrao, telefone.strip()) is not None


def validar_data(data_str):
    """
    Valida se a data está no formato YYYY-MM-DD e é hoje ou futura.
    Retorna (True, objeto_data) se válida, (False, mensagem) se inválida.
    """
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return False, "Data inválida. Use o formato YYYY-MM-DD."

    hoje = datetime.now().date()

    if data_obj < hoje:
        return False, "A data deve ser hoje ou uma data futura."

    return True, data_obj


def horario_dentro_funcionamento(data, horario, duracao_minutos):
    """
    Verifica se um agendamento que inicia em `horario` e dura `duracao_minutos`
    cabe dentro do horário de funcionamento para a data especificada.

    Regras:
    - Segunda a Sábado: 09:00 às 21:00
    - Domingo: 09:00 às 12:00

    Retorna True se o agendamento cabe dentro do horário, False caso contrário.
    """
    try:
        h, m = horario.split(":")
        minutos_inicio = int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return False

    minutos_fin = minutos_inicio + duracao_minutos

    try:
        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
        dia_semana = data_obj.isoweekday()  # 1=Segunda ... 7=Domingo
    except ValueError:
        return False

    if dia_semana == 7:  # Domingo: 09:00 às 12:00
        cierre = 12 * 60
    else:  # Segunda a Sábado: 09:00 às 21:00
        cierre = 21 * 60

    return minutos_inicio >= 9 * 60 and minutos_fin <= cierre


def validar_horario(horario, data=None):
    """
    Verifica se o horário está dentro do horário de funcionamento.
    Segunda a Sábado: 09:00 às 21:00
    Domingo: 09:00 às 12:00
    Se data for fornecida, valida também o dia da semana.
    """
    try:
        h, m = horario.split(":")
        minutos = int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return False

    # Se data for fornecida, verifica o dia da semana
    if data:
        try:
            data_obj = datetime.strptime(data, "%Y-%m-%d").date()
            dia_semana = data_obj.isoweekday()  # 1=Segunda ... 7=Domingo
        except ValueError:
            return False

        if dia_semana == 7:  # Domingo: 09:00 às 12:00
            return 9 * 60 <= minutos < 12 * 60
        else:  # Segunda a Sábado: 09:00 às 21:00
            return 9 * 60 <= minutos < 21 * 60

    # Sem data, aceita o horário geral (09:00-21:00)
    return 9 * 60 <= minutos < 21 * 60


# ============================================
# FUNÇÕES RELACIONADAS A AGENDAMENTOS
# ============================================


def verificar_conflito_horario(data, horario):
    """Verifica se já existe um agendamento para a mesma data e horário."""
    conflito = Agendamento.query.filter_by(data=data, horario=horario).first()
    return conflito is not None


def criar_agendamento(nome, telefone, data, horario, servico,
                      profissional_id=None, cliente_id=None, observacoes=None,
                      plano_id=None):
    """
    Cria e salva um novo agendamento no banco de dados.
    Também cria automaticamente o registro financeiro associado.
    Retorna o objeto Agendamento criado.
    """
    novo_agendamento = Agendamento(
        nome=nome.strip(),
        telefone=telefone.strip(),
        data=data,
        horario=horario,
        servico=servico,
        profissional_id=profissional_id,
        cliente_id=cliente_id,
        plano_id=plano_id,
        observacoes=observacoes
    )
    db.session.add(novo_agendamento)
    db.session.flush()

    # Cria o registro financeiro automaticamente (apenas para agendamentos normais)
    if plano_id is None:
        servico_obj = Servico.query.filter_by(nome=servico).first()
        valor = servico_obj.preco if servico_obj else 0
        financeiro = Financeiro(
            agendamento_id=novo_agendamento.id,
            tipo="agendamento",
            descricao=f"{servico} - {nome.strip()}",
            valor=float(valor or 0),
            status="pendente",
            data_pagamento=data,
        )
        db.session.add(financeiro)

    db.session.commit()
    return novo_agendamento


def criar_agendamento_plano(cliente_id, plano_id, data, horario, profissional_id,
                            observacoes=None):
    """
    Cria um agendamento para um plano com múltiplos serviços (pacote).
    - O pacote de serviços vem do plano_tipo.
    - Cria 1 único Agendamento com N AgendamentoServico.
    - NÃO cria registro financeiro (plano já pago).
    - Consome os benefícios de forma transacional (TUDO ou NADA).
    - Valida titularidade, validade, dias permitidos, benefícios disponíveis,
      profissional ativo, conflito de horário, duração total e horário de funcionamento.

    Retorna (agendamento, None) em sucesso ou (None, mensagem_erro) em falha.
    """
    from sqlalchemy import func

    # ============================================
    # VALIDAÇÃO 1: Plano existe e pertence ao cliente
    # ============================================
    plano = Plano.query.get(plano_id)
    if plano is None:
        return None, "Plano não encontrado."

    # VALIDAÇÃO 2: Titularidade — o plano pertence ao cliente da sessão
    if plano.cliente_id != cliente_id:
        return None, "Este plano não pertence a este cliente."

    # VALIDAÇÃO 3: Plano ativo
    status = atualizar_status_plano(plano)
    if status == "CANCELADO":
        return None, "Este plano foi cancelado."
    if status == "EXPIRADO":
        return None, "Este plano está expirado."
    if status == "ESGOTADO":
        return None, "Este plano está esgotado."

    # VALIDAÇÃO 4: Data dentro da validade
    if not data_dentro_validade(plano, data):
        return None, "Esta data está fora da validade do seu plano."

    # VALIDAÇÃO 5: Dia da semana permitido
    if not dia_permitido_plano(plano, data):
        return None, "Seu plano não permite agendamentos neste dia."

    # VALIDAÇÃO 6: Serviços do pacote
    servicos_pacote = plano.servicos_inclusos
    if not servicos_pacote:
        return None, "Este plano não possui serviços definidos."

    servico_ids = [s.id for s in servicos_pacote]

    # VALIDAÇÃO 7: Benefícios disponíveis (TUDO ou NADA)
    ok, msg = plano.beneficios_disponiveis(servico_ids)
    if not ok:
        return None, msg

    # VALIDAÇÃO 8: Profissional válido e ativo
    profissional = Profissional.query.get(profissional_id)
    if profissional is None or not profissional.ativo:
        return None, "Profissional inválido ou inativo."

    # VALIDAÇÃO 9: Duração total do pacote
    duracao_total = plano.duracao_total
    if duracao_total <= 0:
        return None, "Duração do pacote inválida."

    # VALIDAÇÃO 10: Horário válido (dentro do horário de funcionamento)
    if not validar_horario(horario, data):
        return None, "Horário inválido. Verifique o horário de funcionamento."

    # VALIDAÇÃO 10b: Duração não excede horário de funcionamento
    if not horario_dentro_funcionamento(data, horario, duracao_total):
        return None, "Este horário excede o horário de funcionamento."

    # VALIDAÇÃO 11: Conflito de horário (profissional ocupado)
    if verificar_conflito_profissional(profissional_id, data, horario, duracao_total):
        return None, f"Este horário ({horario}) já está ocupado para {profissional.nome} nesta data."

    # VALIDAÇÃO 12: Bloqueio manual
    if horario_esta_bloqueado(data, horario):
        return None, f"Este horário ({horario}) está bloqueado para esta data."

    # ============================================
    # TUDO VALIDADO — CRIA O AGENDAMENTO + CONSUME BENEFÍCIOS (TRANSAÇÃO)
    # ============================================
    try:
        # Nome do pacote para o campo `servico` (ex: "Corte + Barba")
        nome_pacote = " + ".join(s.nome for s in servicos_pacote)

        # Busca o cliente para nome/telefone
        cliente = Cliente.query.get(cliente_id)
        nome_cliente = cliente.nome if cliente else ""
        telefone_cliente = cliente.telefone if cliente else ""

        # Cria o agendamento (sem financeiro — plano já pago)
        agendamento = Agendamento(
            nome=nome_cliente,
            telefone=telefone_cliente,
            data=data,
            horario=horario,
            servico=nome_pacote,
            profissional_id=profissional_id,
            cliente_id=cliente_id,
            plano_id=plano_id,
            observacoes=observacoes
        )
        db.session.add(agendamento)
        db.session.flush()

        # Cria os vínculos AgendamentoServico
        for sid in servico_ids:
            ag_servico = AgendamentoServico(
                agendamento_id=agendamento.id,
                servico_id=sid
            )
            db.session.add(ag_servico)

        # Consome os benefícios (TUDO ou NADA)
        for sid in servico_ids:
            beneficio = plano.get_beneficio(sid)
            if beneficio and not beneficio.ilimitado:
                beneficio.quantidade_utilizada += 1

        # Atualiza status do plano
        atualizar_status_plano(plano)

        db.session.commit()
        return agendamento, None

    except Exception as e:
        db.session.rollback()
        return None, f"Erro ao criar agendamento: {str(e)}"


def cancelar_agendamento_com_beneficios(agendamento_id):
    """
    Cancela um agendamento e devolve os benefícios do plano.
    - Só devolve benefícios se o agendamento foi feito com plano.
    - Benefícios ilimitados não são devolvidos (não precisam).
    - Remove o registro financeiro se existir.
    """
    agendamento = Agendamento.query.get(agendamento_id)
    if agendamento is None:
        return False, "Agendamento não encontrado."

    # Se tem plano, devolve os benefícios
    if agendamento.plano_id:
        plano = Plano.query.get(agendamento.plano_id)
        if plano:
            # Busca os serviços deste agendamento
            if agendamento.servicos_relacionados:
                for agr in agendamento.servicos_relacionados:
                    beneficio = plano.get_beneficio(agr.servico_id)
                    if beneficio and not beneficio.ilimitado:
                        if beneficio.quantidade_utilizada > 0:
                            beneficio.quantidade_utilizada -= 1
            # Atualiza status do plano
            atualizar_status_plano(plano)

    # Remove o registro financeiro se existir
    financeiro = Financeiro.query.filter_by(agendamento_id=agendamento_id).first()
    if financeiro:
        db.session.delete(financeiro)

    # Remove o agendamento
    db.session.delete(agendamento)
    db.session.commit()
    return True, "Agendamento cancelado e benefícios devolvidos."


# ============================================
# FUNÇÕES DE RELATÓRIOS
# ============================================


def listar_agendamentos_por_periodo(data_inicio, data_fim):
    """Busca agendamentos entre duas datas (inclusive)."""
    return Agendamento.query.filter(
        Agendamento.data >= data_inicio,
        Agendamento.data <= data_fim
    ).order_by(Agendamento.data.asc(), Agendamento.horario.asc()).all()


def calcular_totais_periodo(agendamentos):
    """Calcula totais de um período a partir de uma lista de agendamentos."""
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
    """Retorna todos os profissionais ativos."""
    return Profissional.query.filter_by(ativo=True).all()


def listar_todos_profissionais():
    """Retorna todos os profissionais (ativos e inativos)."""
    return Profissional.query.all()


def buscar_profissional_por_id(profissional_id):
    """Busca um profissional pelo ID."""
    return Profissional.query.get(profissional_id)


def buscar_profissional_por_nome(nome):
    """Busca um profissional pelo nome (case-insensitive)."""
    return Profissional.query.filter(
        db.func.lower(Profissional.nome) == nome.lower()
    ).first()


def criar_profissional(nome, foto=None):
    """Cria e salva um novo profissional."""
    profissional = Profissional(nome=nome, foto=foto, ativo=True)
    db.session.add(profissional)
    db.session.commit()
    return profissional


def atualizar_profissional(profissional_id, nome=None, foto=None, ativo=None):
    """Atualiza os dados de um profissional existente."""
    profissional = buscar_profissional_por_id(profissional_id)
    if profissional is None:
        return None

    if nome is not None:
        profissional.nome = nome
    if foto is not None:
        profissional.foto = foto
    if ativo is not None:
        profissional.ativo = ativo

    db.session.commit()
    return profissional


def excluir_profissional(profissional_id):
    """Exclui um profissional somente se não possuir agendamentos."""
    profissional = buscar_profissional_por_id(profissional_id)
    if profissional is None:
        return False

    tem_agendamentos = Agendamento.query.filter_by(profissional_id=profissional_id).first()
    if tem_agendamentos:
        return False

    db.session.delete(profissional)
    db.session.commit()
    return True


def contar_agendamentos_profissional(profissional_id):
    """Retorna a quantidade de agendamentos de um profissional."""
    return Agendamento.query.filter_by(profissional_id=profissional_id).count()


# ============================================
# FUNÇÕES DE DISPONIBILIDADE INDIVIDUAL
# ============================================


def verificar_conflito_profissional(profissional_id, data, horario_inicio, duracao_minutos):
    """
    Verifica se um profissional já possui agendamento que conflita
    com o intervalo [horario_inicio, horario_inicio + duracao].

    Considera sobreposição real de horários.
    Retorna True se houver conflito, False caso contrário.
    """
    if not profissional_id:
        return False

    def para_minutos(hhmm):
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    inicio_novo = para_minutos(horario_inicio)
    fim_novo = inicio_novo + duracao_minutos

    agendamentos = Agendamento.query.filter_by(
        data=data,
        profissional_id=profissional_id
    ).all()

    for ag in agendamentos:
        # Usa a duração total do agendamento (soma de todos os serviços)
        duracao_existente = ag.duracao_total if ag.duracao_total > 0 else 40

        inicio_existente = para_minutos(ag.horario)
        fim_existente = inicio_existente + duracao_existente

        if inicio_novo < fim_existente and inicio_existente < fim_novo:
            return True

    return False


def listar_horarios_disponiveis(profissional_id, data, duracao_servico):
    """
    Retorna a lista de horários disponíveis para um profissional em uma data,
    considerando a duração do serviço, os agendamentos existentes e
    o horário de funcionamento (Seg-Sáb: 09:00-21:00, Dom: 09:00-12:00).
    """
    # Determina os horários permitidos segundo o dia da semana
    try:
        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
        dia_semana = data_obj.isoweekday()  # 1=Segunda ... 7=Domingo
    except ValueError:
        return []

    if dia_semana == 7:  # Domingo: 09:00 a 12:00
        horarios_permitidos = [
            "09:00", "10:00", "11:00"
        ]
    else:  # Segunda a Sábado: 09:00 a 21:00
        horarios_permitidos = [
            "09:00", "10:00", "11:00", "12:00", "13:00", "14:00",
            "15:00", "16:00", "17:00", "18:00", "19:00", "20:00"
        ]

    resultado = []
    for horario in horarios_permitidos:
        # Verifica que o serviço não exceda o horário de funcionamento
        if not horario_dentro_funcionamento(data, horario, duracao_servico):
            continue

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


def listar_profissionais_disponiveis(data, horario, duracao_minutos):
    """
    Retorna a lista de profissionais ativos que NÃO têm conflito
    no horário especificado, considerando a duração total do pacote.
    """
    profissionais = listar_profissionais()
    disponiveis = []

    for prof in profissionais:
        conflito = verificar_conflito_profissional(
            prof.id, data, horario, duracao_minutos
        )
        bloqueado = horario_esta_bloqueado(data, horario)
        if not conflito and not bloqueado:
            disponiveis.append(prof)

    return disponiveis


# ============================================
# FUNÇÕES RELACIONADAS A CLIENTES
# ============================================


def listar_clientes():
    """Retorna todos os clientes cadastrados."""
    return Cliente.query.order_by(Cliente.nome.asc()).all()


def buscar_cliente_por_id(cliente_id):
    """Busca um cliente pelo ID."""
    return Cliente.query.get(cliente_id)


def buscar_cliente_por_telefone(telefone):
    """Busca um cliente pelo telefone."""
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
    """Retorna todos os bloqueios de uma data específica."""
    return Bloqueio.query.filter_by(data=data).all()


def criar_bloqueio(data, horario, motivo=None):
    """Cria um bloqueio manual de horário."""
    bloqueio = Bloqueio(data=data, horario=horario, motivo=motivo)
    db.session.add(bloqueio)
    db.session.commit()
    return bloqueio


def remover_bloqueio(bloqueio_id):
    """Remove um bloqueio pelo ID."""
    bloqueio = Bloqueio.query.get(bloqueio_id)
    if bloqueio:
        db.session.delete(bloqueio)
        db.session.commit()
        return True
    return False


def horario_esta_bloqueado(data, horario):
    """Verifica se um horário está bloqueado manualmente."""
    return Bloqueio.query.filter_by(data=data, horario=horario).first() is not None


# ============================================
# FUNÇÕES RELACIONADAS A PLANOS
# ============================================


def gerar_codigo_acesso():
    """
    Gera um código de acesso aleatório e seguro para o cliente.
    Usa secrets (criptograficamente seguro) para evitar códigos previsíveis.
    """
    alfabeto = string.ascii_uppercase + string.digits
    alfabeto = alfabeto.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(alfabeto) for _ in range(8))


def criar_planos_predefinidos():
    """
    Cria os 8 planos pré-definidos no catálogo (idempotente).
    Cada plano tipo define seus serviços, quantidades e ilimitados.
    Também atualiza o preço dos planos existentes para os valores oficiais.
    """
    for plano_data in PLANOS_PREDEFINIDOS:
        # Verifica se já existe
        plano_tipo = PlanoTipo.query.filter_by(nome=plano_data["nome"]).first()
        if plano_tipo is None:
            plano_tipo = PlanoTipo(
                nome=plano_data["nome"],
                preco=plano_data["preco"],
                descricao=plano_data["descricao"],
                dias_permitidos=plano_data["dias_permitidos"]
            )
            db.session.add(plano_tipo)
            db.session.flush()

            # Cria os benefícios do plano tipo
            for ben in plano_data["beneficios"]:
                servico = Servico.query.filter_by(nome=ben["servico"]).first()
                if servico:
                    beneficio = PlanoTipoBeneficio(
                        plano_tipo_id=plano_tipo.id,
                        servico_id=servico.id,
                        quantidade=ben["quantidade"],
                        ilimitado=ben["ilimitado"]
                    )
                    db.session.add(beneficio)
        else:
            # Atualiza o preço do plano existente para o valor oficial
            if plano_tipo.preco != plano_data["preco"]:
                plano_tipo.preco = plano_data["preco"]

    db.session.commit()


def listar_planos_tipos():
    """Retorna todos os planos tipos pré-definidos."""
    return PlanoTipo.query.all()


def buscar_plano_tipo_por_id(plano_tipo_id):
    """Busca um plano tipo pelo ID."""
    return PlanoTipo.query.get(plano_tipo_id)


def buscar_plano_tipo_por_nome(nome):
    """Busca um plano tipo pelo nome."""
    return PlanoTipo.query.filter_by(nome=nome).first()


def criar_plano(cliente_id, plano_tipo_id, dias_permitidos=None):
    """
    Cria um novo plano para um cliente a partir de um plano tipo pré-definido.
    - Copia os benefícios do plano tipo para o plano.
    - Gera código de acesso único.
    - Validade: 30 dias a partir de hoje.
    - Status: ATIVO.
    - dias_permitidos: se None, usa o padrão do plano tipo.
    """
    plano_tipo = buscar_plano_tipo_por_id(plano_tipo_id)
    if plano_tipo is None:
        return None

    hoje = datetime.now().date()
    data_validade = hoje + timedelta(days=30)

    # Gera código exclusivo
    codigo = gerar_codigo_acesso()
    while Plano.query.filter_by(codigo_acesso=codigo).first() is not None:
        codigo = gerar_codigo_acesso()

    # Usa os dias do plano tipo se não especificado
    if dias_permitidos is None:
        dias_permitidos = plano_tipo.dias_permitidos

    plano = Plano(
        cliente_id=cliente_id,
        plano_tipo_id=plano_tipo.id,
        nome=plano_tipo.nome,
        preco=plano_tipo.preco,
        data_inicio=hoje.strftime("%Y-%m-%d"),
        data_validade=data_validade.strftime("%Y-%m-%d"),
        status="ATIVO",
        dias_permitidos=dias_permitidos,
        codigo_acesso=codigo,
    )
    db.session.add(plano)
    db.session.flush()

    # Copia os benefícios do plano tipo para o plano
    for ben_tipo in plano_tipo.beneficios:
        beneficio = PlanoBeneficio(
            plano_id=plano.id,
            servico_id=ben_tipo.servico_id,
            quantidade=ben_tipo.quantidade,
            quantidade_utilizada=0,
            ilimitado=ben_tipo.ilimitado
        )
        db.session.add(beneficio)

    db.session.flush()

    # ============================================
    # RECEITA DA VENDA DO PLANO
    # Reutiliza a tabela Financeiro (sem criar sistema paralelo).
    # Valor convertido de centavos para reais: 9000 -> R$ 90,00.
    # SOMENTE status "pago" entra no faturamento.
    # ============================================
    valor_reais = float(plano_tipo.preco or 0) / 100.0
    receita_plano = Financeiro(
        plano_id=plano.id,
        tipo="plano",
        descricao=f"Venda de plano {plano_tipo.nome}",
        valor=round(valor_reais, 2),
        status="pago",
        forma_pagamento="dinheiro",
        data_pagamento=hoje.strftime("%Y-%m-%d"),
    )
    db.session.add(receita_plano)

    db.session.commit()
    return plano


def buscar_plano_por_cliente(cliente_id):
    """Busca o plano de um cliente pelo ID do cliente."""
    return Plano.query.filter_by(cliente_id=cliente_id).first()


def buscar_plano_por_id(plano_id):
    """Busca um plano pelo ID."""
    return Plano.query.get(plano_id)


def buscar_plano_por_codigo(codigo):
    """Busca um plano pelo código de acesso."""
    return Plano.query.filter_by(codigo_acesso=codigo).first()


def listar_planos():
    """Retorna todos os planos cadastrados."""
    return Plano.query.order_by(Plano.criado_em.desc()).all()


def atualizar_status_plano(plano):
    """
    Atualiza o status do plano com base nas regras atuais:
    - CANCELADO: se foi cancelado manualmente
    - EXPIRADO: se a validade passou
    - ESGOTADO: se todos os benefícios finitos acabaram
    - ATIVO: caso contrário
    """
    if plano.status == "CANCELADO":
        return plano.status

    hoje = datetime.now().date()
    validade = datetime.strptime(plano.data_validade, "%Y-%m-%d").date()

    if validade < hoje:
        plano.status = "EXPIRADO"
    elif not plano.tem_beneficio_ilimitado and all(
        not b.disponivel for b in plano.beneficios
    ):
        plano.status = "ESGOTADO"
    else:
        plano.status = "ATIVO"

    db.session.commit()
    return plano.status


def verificar_plano_valido(plano):
    """
    Verifica se um plano pode ser utilizado para agendamento.
    Retorna (True, None) se válido, ou (False, mensagem_erro).
    """
    if plano is None:
        return False, "Plano não encontrado."

    status = atualizar_status_plano(plano)

    if status == "CANCELADO":
        return False, "Este plano foi cancelado."
    if status == "EXPIRADO":
        return False, "Este plano está expirado."
    if status == "ESGOTADO":
        return False, "Este plano não possui mais benefícios disponíveis."

    return True, None


def dia_permitido_plano(plano, data_str):
    """
    Verifica se uma data está dentro dos dias permitidos do plano.
    data_str: data no formato YYYY-MM-DD
    Convenção: 1=Segunda ... 7=Domingo (isoweekday)
    """
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return False

    dia_semana = data_obj.isoweekday()
    return dia_semana in plano.dias_permitidos_lista


def data_dentro_validade(plano, data_str):
    """Verifica se uma data está dentro da validade do plano."""
    try:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
        validade = datetime.strptime(plano.data_validade, "%Y-%m-%d").date()
    except ValueError:
        return False

    return data_obj <= validade


def consumir_beneficios(plano_id, servico_ids):
    """
    Consome 1 unidade de cada benefício para os serviços especificados.
    Só consome benefícios finitos (não ilimitados).
    """
    plano = buscar_plano_por_id(plano_id)
    if plano is None:
        return False

    for sid in servico_ids:
        beneficio = plano.get_beneficio(sid)
        if beneficio and not beneficio.ilimitado:
            beneficio.quantidade_utilizada += 1

    atualizar_status_plano(plano)
    return True


def devolver_beneficios(plano_id, servico_ids):
    """
    Devolve 1 unidade de cada benefício para os serviços especificados.
    Só devolve benefícios finitos (não ilimitados).
    """
    plano = buscar_plano_por_id(plano_id)
    if plano is None:
        return False

    for sid in servico_ids:
        beneficio = plano.get_beneficio(sid)
        if beneficio and not beneficio.ilimitado:
            if beneficio.quantidade_utilizada > 0:
                beneficio.quantidade_utilizada -= 1

    atualizar_status_plano(plano)
    return True


def renovar_plano(plano_id):
    """
    Renova um plano: restaura todos os benefícios, nova validade de 30 dias, status ATIVO.
    Registra a receita de renovação (tipo="renovacao_plano") sem duplicar a venda original.
    """
    plano = buscar_plano_por_id(plano_id)
    if plano is None:
        return None

    hoje = datetime.now().date()
    plano.data_inicio = hoje.strftime("%Y-%m-%d")
    plano.data_validade = (hoje + timedelta(days=30)).strftime("%Y-%m-%d")
    plano.status = "ATIVO"

    # Restaura todos os benefícios
    for beneficio in plano.beneficios:
        if not beneficio.ilimitado:
            beneficio.quantidade_utilizada = 0

    db.session.flush()

    # ============================================
    # RECEITA DE RENOVAÇÃO DO PLANO
    # Reutiliza a tabela Financeiro. A venda original (tipo="plano")
    # é preservada; a renovação entra como nova receita.
    # ============================================
    plano_tipo = plano.plano_tipo
    valor_reais = float(plano_tipo.preco or 0) / 100.0 if plano_tipo else 0.0
    receita_renovacao = Financeiro(
        plano_id=plano.id,
        tipo="renovacao_plano",
        descricao=f"Renovação de plano {plano.nome}",
        valor=round(valor_reais, 2),
        status="pago",
        forma_pagamento="dinheiro",
        data_pagamento=hoje.strftime("%Y-%m-%d"),
    )
    db.session.add(receita_renovacao)

    db.session.commit()
    return plano


def cancelar_plano(plano_id):
    """Cancela um plano (status CANCELADO)."""
    plano = buscar_plano_por_id(plano_id)
    if plano is None:
        return False

    plano.status = "CANCELADO"
    db.session.commit()
    return True


def calcular_duracao_pacote(servico_ids):
    """
    Calcula a duração total de um pacote de serviços (soma das durações).
    """
    total = 0
    for sid in servico_ids:
        servico = Servico.query.get(sid)
        if servico:
            total += servico.tempo
    return total


# ============================================
# FUNÇÕES DE INICIALIZAÇÃO
# ============================================


def criar_banco_e_popular():
    """
    Cria as tabelas no banco de dados e insere os serviços
    iniciais e planos pré-definidos (caso ainda não existam).
    """
    db.create_all()

    # ============================================
    # SERVIÇOS INICIALES
    # ============================================
    if Servico.query.first() is None:
        servicos_iniciales = [
            {"nome": "Corte", "preco": 40, "tempo": 40},
            {"nome": "Barba", "preco": 25, "tempo": 25},
            {"nome": "Limpeza", "preco": 30, "tempo": 30},
            {"nome": "Sobrancelha", "preco": 20, "tempo": 20},
            {"nome": "Combo Premium", "preco": 80, "tempo": 90},
        ]

        for dados in servicos_iniciales:
            servico = Servico(
                nome=dados["nome"],
                preco=dados["preco"],
                tempo=dados["tempo"],
            )
            db.session.add(servico)

        db.session.commit()

    # ============================================
    # PROFESIONAL PADRÃO "HARRISON"
    # ============================================
    if buscar_profissional_por_nome("HARRISON") is None:
        harrison = Profissional(
            nome="HARRISON",
            foto=None,
            ativo=True
        )
        db.session.add(harrison)
        db.session.commit()

    # ============================================
    # PLANOS PRÉ-DEFINIDOS
    # ============================================
    criar_planos_predefinidos()