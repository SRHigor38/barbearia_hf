# ============================================
# ROTAS PÚBLICAS
# ============================================
# Rotas acessíveis por qualquer usuário (sem login).
# Fluxo de agendamento em etapas:
#   1. Serviço → 2. Profissional → 3. Data → 4. Horário → 5. Confirmação
#
# Fluxo de agendamento com PLANO:
#   1. Telefone + Chave → 2. Dia → 3. Horário → 4. Profissional → 5. Agendamento direto

from flask import render_template, request, redirect, url_for, flash, jsonify, session
from routes import main_bp
from services.barbearia_service import (
    listar_servicos_do_banco,
    contar_servicos,
    servico_existe_no_banco,
    buscar_servico_por_nome,
    validar_telefone,
    validar_data,
    validar_horario,
    horario_dentro_funcionamento,
    verificar_conflito_profissional,
    listar_horarios_disponiveis,
    listar_profissionais_disponiveis,
    criar_agendamento,
    criar_agendamento_plano,
    cancelar_agendamento_com_beneficios,
    listar_profissionais,
    buscar_profissional_por_id,
    horario_esta_bloqueado,
    criar_cliente,
    buscar_cliente_por_id,
    buscar_cliente_por_telefone,
    buscar_plano_por_cliente,
    buscar_plano_por_id,
    dia_permitido_plano,
    data_dentro_validade,
    atualizar_status_plano,
)


# ============================================
# ROTAS PÚBLICAS
# ============================================


@main_bp.route("/")
def inicio():
    """Rota principal: exibe a página inicial com todos os serviços."""
    servicos = listar_servicos_do_banco()
    total_servicos = contar_servicos()

    return render_template(
        "index.html",
        servicos=servicos,
        total_servicos=total_servicos
    )


# ============================================
# FLUXO NORMAL DE AGENDAMENTO (sem plano)
# ============================================


@main_bp.route("/agendamento", methods=["GET", "POST"])
def agendamento():
    """
    Rota de agendamento em etapas (fluxo NORMAL — sem plano).
    - GET:  Exibe o fluxo de agendamento (serviço → profissional → data → horário → confirmação).
    - POST: Processa os dados e cria o agendamento.
    """

    if request.method == "GET":
        nome_servico = request.args.get("servico")
        servico_encontrado = buscar_servico_por_nome(nome_servico)

        if servico_encontrado is None:
            flash("Serviço não encontrado. Selecione um serviço válido.", "warning")
            return redirect(url_for("main.inicio"))

        profissionais = listar_profissionais()

        dados_servico = {
            "preco": servico_encontrado.preco,
            "tempo": servico_encontrado.tempo,
            "descricao": servico_encontrado.descricao,
            "categoria": servico_encontrado.categoria,
            "badge": servico_encontrado.badge,
            "imagem": servico_encontrado.imagem,
        }

        return render_template(
            "agendamento.html",
            servico=nome_servico,
            dados=dados_servico,
            profissionais=profissionais
        )

    # POST: processa o agendamento normal
    nome = request.form.get("nome", "")
    telefone = request.form.get("telefone", "")
    data = request.form.get("data", "")
    horario = request.form.get("horario", "")
    nome_servico = request.form.get("servico", "")
    profissional_id = request.form.get("profissional_id", "")
    observacoes = request.form.get("observacoes", "")

    # Validações
    if not nome_servico or not servico_existe_no_banco(nome_servico):
        flash("Serviço inválido.", "error")
        return redirect(url_for("main.inicio"))

    if not nome or not nome.strip():
        flash("O nome é obrigatório.", "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    if not telefone or not validar_telefone(telefone):
        flash("Telefone inválido. Use o formato com DDD (ex: 11999998888 ou (11) 99999-8888).", "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    data_valida, resultado_data = validar_data(data)
    if not data_valida:
        flash(resultado_data, "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    if not validar_horario(horario, data):
        flash("Horário inválido. Verifique o horário de funcionamento.", "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    profissional_id_int = int(profissional_id) if profissional_id.isdigit() else None
    if profissional_id_int is None:
        flash("Selecione um profissional.", "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    profissional = buscar_profissional_por_id(profissional_id_int)
    if profissional is None or not profissional.ativo:
        flash("Profissional inválido ou inativo.", "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    servico_obj = buscar_servico_por_nome(nome_servico)
    duracao_servico = servico_obj.tempo if servico_obj else 40

    if verificar_conflito_profissional(profissional_id_int, data, horario, duracao_servico):
        flash(f"Este horário ({horario}) já está ocupado para {profissional.nome} na data {data}. Escolha outro horário.", "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    if horario_esta_bloqueado(data, horario):
        flash(f"Este horário ({horario}) não está disponível para a data {data}. Escolha outro horário.", "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    # Cria o cliente e o agendamento
    cliente = criar_cliente(nome=nome, telefone=telefone)
    criar_agendamento(
        nome, telefone, data, horario, nome_servico,
        profissional_id=profissional_id_int,
        cliente_id=cliente.id,
        observacoes=observacoes or None
    )

    flash("Agendamento realizado com sucesso!", "success")
    return render_template(
        "confirmacao.html",
        nome=nome.strip(),
        telefone=telefone,
        data=data,
        horario=horario,
        servico=nome_servico
    )


@main_bp.route("/api/horarios")
def api_horarios():
    """
    API interna: retorna os horários disponíveis para um profissional
    em uma data, considerando a duração do serviço.
    """
    data = request.args.get("data", "")
    profissional_id = request.args.get("profissional_id", "")
    servico_nome = request.args.get("servico", "")

    duracao = 40
    if servico_nome:
        servico_obj = buscar_servico_por_nome(servico_nome)
        duracao = servico_obj.tempo if servico_obj else 40

    profissional_id_int = int(profissional_id) if profissional_id.isdigit() else None
    horarios = listar_horarios_disponiveis(profissional_id_int, data, duracao)

    return jsonify({"horarios": horarios})


# ============================================
# ÁREA "MEU PLANO" (acesso do cliente via telefone + chave)
# ============================================


@main_bp.route("/meu-plano", methods=["GET", "POST"])
def meu_plano():
    """
    Página de acesso do cliente ao plano.
    GET:  Exibe formulário (Telefone + Código).
    POST: Valida telefone + código e cria sessão.
    """
    if "cliente_plano_id" in session:
        return redirect(url_for("main.meu_plano_area"))

    if request.method == "POST":
        telefone = request.form.get("telefone", "").strip()
        codigo = request.form.get("codigo", "").strip()

        if not telefone or not codigo:
            flash("Informe telefone e código de acesso.", "error")
            return render_template("meu_plano.html")

        # Busca cliente pelo telefone
        cliente = buscar_cliente_por_telefone(telefone)
        if cliente is None:
            flash("Cliente não encontrado. Verifique o telefone.", "error")
            return render_template("meu_plano.html")

        # Busca o plano do cliente
        plano = buscar_plano_por_cliente(cliente.id)
        if plano is None:
            flash("Nenhum plano encontrado para este cliente.", "error")
            return render_template("meu_plano.html")

        # Verifica o código de acesso
        if plano.codigo_acesso != codigo:
            flash("Código de acesso inválido.", "error")
            return render_template("meu_plano.html")

        # Cria sessão segura do cliente
        session["cliente_plano_id"] = cliente.id
        session["cliente_plano_nome"] = cliente.nome

        flash("Acesso liberado! Bem-vindo(a).", "success")
        return redirect(url_for("main.meu_plano_area"))

    return render_template("meu_plano.html")


@main_bp.route("/meu-plano/area")
def meu_plano_area():
    """
    Área do cliente com o plano.
    Mostra benefícios por serviço, validade, dias permitidos e botão de agendamento.
    """
    if "cliente_plano_id" not in session:
        flash("Faça login no seu plano para acessar.", "warning")
        return redirect(url_for("main.meu_plano"))

    cliente_id = session["cliente_plano_id"]
    cliente = buscar_cliente_por_id(cliente_id)
    if cliente is None:
        session.pop("cliente_plano_id", None)
        session.pop("cliente_plano_nome", None)
        return redirect(url_for("main.meu_plano"))

    plano = buscar_plano_por_cliente(cliente_id)
    if plano is None:
        flash("Nenhum plano encontrado para este cliente.", "error")
        return redirect(url_for("main.meu_plano"))

    # Atualiza status real (expirado/esgotado)
    atualizar_status_plano(plano)

    # Nomes dos dias da semana (1=Segunda ... 7=Domingo)
    dias_nomes = ["", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    dias_permitidos_nomes = [dias_nomes[d] for d in plano.dias_permitidos_lista]

    # Benefícios por serviço
    beneficios_info = []
    for ben in plano.beneficios:
        beneficios_info.append({
            "servico": ben.servico.nome,
            "ilimitado": ben.ilimitado,
            "quantidade": ben.quantidade,
            "utilizado": ben.quantidade_utilizada,
            "restante": ben.restante,
        })

    # Duração total do pacote
    duracao_total = plano.duracao_total

    return render_template(
        "meu_plano_area.html",
        cliente=cliente,
        plano=plano,
        dias_permitidos_nomes=dias_permitidos_nomes,
        beneficios_info=beneficios_info,
        duracao_total=duracao_total,
    )


@main_bp.route("/meu-plano/logout")
def meu_plano_logout():
    """Encerra a sessão do cliente."""
    session.pop("cliente_plano_id", None)
    session.pop("cliente_plano_nome", None)
    flash("Sessão encerrada.", "info")
    return redirect(url_for("main.meu_plano"))


# ============================================
# FLUXO DE AGENDAMENTO COM PLANO
# ============================================


@main_bp.route("/meu-plano/agendar", methods=["GET", "POST"])
def agendar_plano():
    """
    Fluxo de agendamento para clientes com plano.
    - GET:  Exibe o formulário (Dia → Horário → Profissional).
    - POST: Cria o agendamento diretamente (sem etapa de confirmação).
    """
    # Validação de sessão
    if "cliente_plano_id" not in session:
        flash("Faça login no seu plano para acessar.", "warning")
        return redirect(url_for("main.meu_plano"))

    cliente_id = session["cliente_plano_id"]
    cliente = buscar_cliente_por_id(cliente_id)
    if cliente is None:
        session.pop("cliente_plano_id", None)
        session.pop("cliente_plano_nome", None)
        return redirect(url_for("main.meu_plano"))

    plano = buscar_plano_por_cliente(cliente_id)
    if plano is None:
        flash("Nenhum plano encontrado para este cliente.", "error")
        return redirect(url_for("main.meu_plano"))

    # Valida titularidade (o plano pertence ao cliente da sessão)
    if plano.cliente_id != cliente_id:
        flash("Este plano não pertence a este cliente.", "error")
        return redirect(url_for("main.meu_plano"))

    # Atualiza status
    status = atualizar_status_plano(plano)
    if status == "CANCELADO":
        flash("Este plano foi cancelado.", "error")
        return redirect(url_for("main.meu_plano_area"))
    if status == "EXPIRADO":
        flash("Este plano está expirado.", "error")
        return redirect(url_for("main.meu_plano_area"))
    if status == "ESGOTADO":
        flash("Este plano está esgotado.", "error")
        return redirect(url_for("main.meu_plano_area"))

    # Serviços do pacote
    servicos_pacote = plano.servicos_inclusos
    if not servicos_pacote:
        flash("Este plano não possui serviços definidos.", "error")
        return redirect(url_for("main.meu_plano_area"))

    # Duração total do pacote
    duracao_total = plano.duracao_total

    # Nomes dos dias da semana (1=Segunda ... 7=Domingo)
    dias_nomes = ["", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    dias_permitidos_nomes = [dias_nomes[d] for d in plano.dias_permitidos_lista]

    if request.method == "POST":
        data = request.form.get("data", "")
        horario = request.form.get("horario", "")
        profissional_id = request.form.get("profissional_id", "")
        observacoes = request.form.get("observacoes", "")

        profissional_id_int = int(profissional_id) if profissional_id.isdigit() else None

        # Cria o agendamento com validações completas no backend
        agendamento, erro = criar_agendamento_plano(
            cliente_id=cliente_id,
            plano_id=plano.id,
            data=data,
            horario=horario,
            profissional_id=profissional_id_int,
            observacoes=observacoes or None
        )

        if erro:
            flash(erro, "error")
            return redirect(url_for("main.agendar_plano"))

        # Sucesso — mostra confirmação
        flash("Agendamento realizado com sucesso!", "success")
        return render_template(
            "confirmacao.html",
            agendamento=agendamento,
            plano=plano,
            cliente=cliente,
            data=data,
            horario=horario,
            profissional=buscar_profissional_por_id(profissional_id_int),
            servicos_pacote=servicos_pacote,
        )

    # GET: exibe o formulário
    profissionais = listar_profissionais()

    return render_template(
        "agendamento_plano.html",
        plano=plano,
        cliente=cliente,
        servicos_pacote=servicos_pacote,
        duracao_total=duracao_total,
        dias_permitidos=plano.dias_permitidos_lista,
        dias_permitidos_nomes=dias_permitidos_nomes,
        profissionais=profissionais,
    )


@main_bp.route("/api/horarios-plano")
def api_horarios_plano():
    """
    API para o fluxo de plano: retorna horários disponíveis
    considerando a duração total do pacote e todos os profissionais.
    Um horário está disponível se PELO MENOS UM profissional ativo estiver livre.
    """
    data = request.args.get("data", "")
    try:
        duracao = int(request.args.get("duracao", "40"))
    except (TypeError, ValueError):
        duracao = 40

    # Horários segundo o dia da semana
    try:
        from datetime import datetime
        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
        dia_semana = data_obj.isoweekday()  # 1=Segunda ... 7=Domingo
    except ValueError:
        return jsonify({"horarios": []})

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
        # Verifica que a duração não exceda o horário de funcionamento
        if not horario_dentro_funcionamento(data, horario, duracao):
            continue

        # Verifica se pelo menos um profissional está disponível
        profs_disponiveis = listar_profissionais_disponiveis(data, horario, duracao)
        bloqueado = horario_esta_bloqueado(data, horario)

        resultado.append({
            "horario": horario,
            "disponivel": len(profs_disponiveis) > 0 and not bloqueado,
            "profissionais_disponiveis": [p.id for p in profs_disponiveis],
        })

    return jsonify({"horarios": resultado})


@main_bp.route("/api/profissionais-disponiveis")
def api_profissionais_disponiveis():
    """
    API para o fluxo de plano: retorna profissionais disponíveis
    em uma data e horário específicos, considerando a duração do pacote.
    """
    data = request.args.get("data", "")
    horario = request.args.get("horario", "")
    try:
        duracao = int(request.args.get("duracao", "40"))
    except (TypeError, ValueError):
        duracao = 40

    profissionais = listar_profissionais_disponiveis(data, horario, duracao)

    resultado = []
    for prof in profissionais:
        resultado.append({
            "id": prof.id,
            "nome": prof.nome,
            "foto": prof.foto,
        })

    return jsonify({"profissionais": resultado})


# ============================================
# CANCELAMENTO DE AGENDAMENTO
# ============================================


@main_bp.route("/agendamento/cancelar/<int:agendamento_id>", methods=["POST"])
def cancelar_agendamento(agendamento_id):
    """
    Cancela um agendamento.
    - Se for de plano: devolve os benefícios.
    - Se for normal: apenas remove.
    """
    sucesso, mensagem = cancelar_agendamento_com_beneficios(agendamento_id)
    if sucesso:
        flash(mensagem, "success")
    else:
        flash(mensagem, "error")
    return redirect(url_for("main.inicio"))
