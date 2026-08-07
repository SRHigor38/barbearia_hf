# ============================================
# ROTAS PÚBLICAS
# ============================================
# Rotas acessíveis por qualquer usuário (sem login).
# Fluxo de agendamento em etapas:
#   1. Serviço → 2. Profissional → 3. Data → 4. Horário → 5. Confirmação

from flask import render_template, request, redirect, url_for, flash, jsonify
from routes import main_bp
from services.barbearia_service import (
    listar_servicos_do_banco,
    contar_servicos,
    servico_existe_no_banco,
    buscar_servico_por_nome,
    validar_telefone,
    validar_data,
    validar_horario,
    verificar_conflito_horario,
    criar_agendamento,
    listar_profissionais,
    buscar_profissional_por_id,
    horario_esta_bloqueado,
    criar_cliente,
)


@main_bp.route("/")
def inicio():
    """
    Rota principal: exibe a página inicial com todos os serviços.
    """
    servicos = listar_servicos_do_banco()
    total_servicos = contar_servicos()

    return render_template(
        "index.html",
        servicos=servicos,
        total_servicos=total_servicos
    )


@main_bp.route("/agendamento", methods=["GET", "POST"])
def agendamento():
    """
    Rota de agendamento em etapas.
    - GET:  Exibe o fluxo de agendamento (serviço → profissional → data → horário).
    - POST: Processa os dados e mostra confirmação.
    """

    if request.method == "GET":
        # ============================================
        # PASSO 1: Pega o serviço da URL
        # ============================================
        nome_servico = request.args.get("servico")

        # ============================================
        # PASSO 2: Busca o serviço no banco de dados
        # ============================================
        servico_encontrado = buscar_servico_por_nome(nome_servico)

        # ============================================
        # PASSO 3: Valida se o serviço existe
        # ============================================
        if servico_encontrado is None:
            flash("Serviço não encontrado. Selecione um serviço válido.", "warning")
            return redirect(url_for("main.inicio"))

        # ============================================
        # PASSO 4: Busca profissionais disponíveis
        # ============================================
        profissionais = listar_profissionais()

        # ============================================
        # PASSO 5: Prepara os dados para o template
        # ============================================
        dados_servico = {
            "preco": servico_encontrado.preco,
            "tempo": servico_encontrado.tempo,
            "descricao": servico_encontrado.descricao,
            "categoria": servico_encontrado.categoria,
            "badge": servico_encontrado.badge,
            "imagem": servico_encontrado.imagem,
        }

        # ============================================
        # PASSO 6: Renderiza o formulário em etapas
        # ============================================
        return render_template(
            "agendamento.html",
            servico=nome_servico,
            dados=dados_servico,
            profissionais=profissionais
        )

    # ============================================
    # SE CHEGOU AQUI, É UMA REQUISIÇÃO POST
    # ============================================

    # ============================================
    # PASSO 1: Pega os dados enviados pelo formulário
    # ============================================
    nome = request.form["nome"]
    telefone = request.form["telefone"]
    data = request.form["data"]
    horario = request.form["horario"]
    nome_servico = request.form["servico"]
    profissional_id = request.form.get("profissional_id", "")
    observacoes = request.form.get("observacoes", "")

    # ============================================
    # PASSO 2: Valida se o serviço existe
    # ============================================
    if not servico_existe_no_banco(nome_servico):
        flash("Serviço inválido.", "error")
        return redirect(url_for("main.inicio"))

    # ============================================
    # PASSO 3: Valida o nome
    # ============================================
    if not nome.strip():
        flash("O nome é obrigatório.", "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    # ============================================
    # PASSO 4: Valida o telefone
    # ============================================
    if not validar_telefone(telefone):
        flash(
            "Telefone inválido. Use o formato com DDD "
            "(ex: 11999998888 ou (11) 99999-8888).",
            "error"
        )
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    # ============================================
    # PASSO 5: Valida a data
    # ============================================
    data_valida, resultado_data = validar_data(data)
    if not data_valida:
        flash(resultado_data, "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    # ============================================
    # PASSO 6: Valida o horário
    # ============================================
    if not validar_horario(horario):
        flash("Horário inválido. Selecione um horário disponível.", "error")
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    # ============================================
    # PASSO 7: Valida conflito de horário
    # ============================================
    if verificar_conflito_horario(data, horario):
        flash(
            f"Este horário ({horario}) já está agendado para "
            f"a data {data}. Escolha outro horário.",
            "error"
        )
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    # ============================================
    # PASSO 8: Valida bloqueio manual
    # ============================================
    if horario_esta_bloqueado(data, horario):
        flash(
            f"Este horário ({horario}) não está disponível para "
            f"a data {data}. Escolha outro horário.",
            "error"
        )
        return redirect(url_for("main.agendamento") + f"?servico={nome_servico}")

    # ============================================
    # PASSO 9: Cria/vincula cliente automaticamente
    # ============================================
    cliente = criar_cliente(nome=nome, telefone=telefone)

    # ============================================
    # PASSO 10: Salva o agendamento no banco de dados
    # ============================================
    profissional_id_int = int(profissional_id) if profissional_id.isdigit() else None

    criar_agendamento(
        nome, telefone, data, horario, nome_servico,
        profissional_id=profissional_id_int,
        cliente_id=cliente.id,
        observacoes=observacoes or None
    )

    # ============================================
    # PASSO 11: Tudo validado e salvo — mostra confirmação
    # ============================================
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
    API interna: retorna os horários disponíveis para uma data.
    Usada pelo front-end para atualizar o calendário dinamicamente.
    """
    data = request.args.get("data", "")
    horarios_permitidos = [
        "08:00", "09:00", "10:00", "11:00",
        "13:00", "14:00", "15:00", "16:00", "17:00"
    ]

    horarios = []
    for horario in horarios_permitidos:
        ocupado = verificar_conflito_horario(data, horario)
        bloqueado = horario_esta_bloqueado(data, horario)
        horarios.append({
            "horario": horario,
            "disponivel": not ocupado and not bloqueado,
            "ocupado": ocupado,
            "bloqueado": bloqueado,
        })

    return jsonify({"horarios": horarios})