# ============================================
# ROTAS PÚBLICAS
# ============================================
# Rotas acessíveis por qualquer usuário (sem login).

from flask import render_template, request, redirect, url_for, flash
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
    Rota de agendamento.
    - GET:  Exibe o formulário de agendamento para um serviço específico.
    - POST: Processa os dados do formulário, valida e mostra confirmação.
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
        # PASSO 4: Prepara os dados para o template
        # ============================================
        dados_servico = {
            "preco": servico_encontrado.preco,
            "tempo": servico_encontrado.tempo,
        }

        # ============================================
        # PASSO 5: Renderiza o formulário
        # ============================================
        return render_template(
            "agendamento.html",
            servico=nome_servico,
            dados=dados_servico
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
    # PASSO 8: Salva o agendamento no banco de dados
    # ============================================
    criar_agendamento(nome, telefone, data, horario, nome_servico)

    # ============================================
    # PASSO 9: Tudo validado e salvo — mostra confirmação
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