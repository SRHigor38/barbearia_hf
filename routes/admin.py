# ============================================
# ROTAS ADMINISTRATIVAS
# ============================================
# Rotas protegidas por login. Acessíveis apenas por administradores.

from flask import render_template, request, redirect, url_for, flash, session, current_app
from models import db
from models.servico import Servico
from models.agendamento import Agendamento
from models.admin import Admin
from routes import admin_bp
from services.barbearia_service import (
    contar_servicos,
    servico_existe_no_banco,
)


# ============================================
# FUNÇÃO AUXILIAR: login_necessario()
# ============================================


def login_necessario():
    """
    Verifica se o usuário está logado.
    Se não estiver, redireciona para a página de login.
    """
    if "admin_id" not in session:
        flash("Faça login para acessar o painel.", "warning")
        return redirect(url_for("admin.login"))


# ============================================
# LOGIN
# ============================================


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Página de login do administrador.
    GET:  Exibe o formulário de login.
    POST: Verifica usuário e senha e faz login.
    """
    if request.method == "GET":
        if "admin_id" in session:
            return redirect(url_for("admin.inicio"))
        return render_template("admin_login.html")

    # Processamento do POST (login)
    usuario = request.form.get("usuario", "").strip()
    senha = request.form.get("senha", "")

    if not usuario or not senha:
        flash("Preencha usuário e senha.", "error")
        return render_template("admin_login.html")

    admin = Admin.query.filter_by(usuario=usuario).first()

    # Usa o bcrypt que foi configurado na aplicação (app.bcrypt)
    # current_app dá acesso à aplicação Flask atual
    bcrypt = current_app.bcrypt

    if admin is None or not bcrypt.check_password_hash(admin.senha_hash, senha):
        flash("Usuário ou senha inválidos.", "error")
        return render_template("admin_login.html")

    # Login bem-sucedido
    session["admin_id"] = admin.id
    session["admin_usuario"] = admin.usuario

    flash(f"Bem-vindo, {admin.usuario}!", "success")
    return redirect(url_for("admin.inicio"))


# ============================================
# LOGOUT
# ============================================


@admin_bp.route("/logout")
def logout():
    """
    Faz logout do administrador.
    Limpa os dados da sessão e redireciona para o login.
    """
    session.pop("admin_id", None)
    session.pop("admin_usuario", None)
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("admin.login"))


# ============================================
# INÍCIO DO PAINEL
# ============================================


@admin_bp.route("/")
def inicio():
    """
    Dashboard do painel administrativo.
    Mostra cards com indicadores e tabela dos últimos agendamentos.
    """
    check = login_necessario()
    if check:
        return check

    from datetime import datetime, date

    hoje = date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")
    mes_atual = hoje.strftime("%Y-%m")

    # ============================================
    # INDICADORES
    # ============================================

    # Total de serviços cadastrados
    total_servicos = contar_servicos()

    # Total de agendamentos (todos)
    total_agendamentos = Agendamento.query.count()

    # Agendamentos de hoje
    agendamentos_hoje = Agendamento.query.filter(
        Agendamento.data == hoje_str
    ).count()

    # Agendamentos do mês atual
    agendamentos_mes = Agendamento.query.filter(
        Agendamento.data.like(f"{mes_atual}%")
    ).count()

    # Clientes atendidos (agendamentos únicos por nome)
    clientes_atendidos = Agendamento.query.with_entities(
        Agendamento.nome
    ).distinct().count()

    # Faturamento (simulado com base nos serviços)
    # Busca todos os agendamentos de hoje e calcula o valor
    agendamentos_hoje_lista = Agendamento.query.filter_by(data=hoje_str).all()
    faturamento_hoje = 0
    for ag in agendamentos_hoje_lista:
        servico = Servico.query.filter_by(nome=ag.servico).first()
        if servico:
            faturamento_hoje += servico.preco

    # Faturamento do mês
    agendamentos_mes_lista = Agendamento.query.filter(
        Agendamento.data.like(f"{mes_atual}%")
    ).all()
    faturamento_mes = 0
    for ag in agendamentos_mes_lista:
        servico = Servico.query.filter_by(nome=ag.servico).first()
        if servico:
            faturamento_mes += servico.preco

    # ============================================
    # ÚLTIMOS AGENDAMENTOS
    # ============================================
    ultimos_agendamentos = Agendamento.query.order_by(
        Agendamento.criado_em.desc()
    ).limit(5).all()

    return render_template(
        "admin_dashboard.html",
        total_servicos=total_servicos,
        total_agendamentos=total_agendamentos,
        agendamentos_hoje=agendamentos_hoje,
        agendamentos_mes=agendamentos_mes,
        clientes_atendidos=clientes_atendidos,
        faturamento_hoje=faturamento_hoje,
        faturamento_mes=faturamento_mes,
        ultimos_agendamentos=ultimos_agendamentos
    )


# ============================================
# GERENCIAR AGENDAMENTOS
# ============================================


@admin_bp.route("/agendamentos")
def listar_agendamentos():
    """
    Lista todos os agendamentos cadastrados,
    ordenados do mais recente para o mais antigo.
    """
    check = login_necessario()
    if check:
        return check

    agendamentos = Agendamento.query.order_by(
        Agendamento.criado_em.desc()
    ).all()

    return render_template(
        "admin_agendamentos.html",
        agendamentos=agendamentos
    )


@admin_bp.route("/agendamentos/excluir/<int:agendamento_id>")
def excluir_agendamento(agendamento_id):
    """
    Exclui um agendamento pelo ID.
    Também remove o registro financeiro associado.
    """
    check = login_necessario()
    if check:
        return check

    from models.financeiro import Financeiro

    agendamento = Agendamento.query.get(agendamento_id)

    if agendamento is None:
        flash("Agendamento não encontrado.", "error")
    else:
        # Remove o registro financeiro associado (se existir)
        financeiro = Financeiro.query.filter_by(agendamento_id=agendamento_id).first()
        if financeiro:
            db.session.delete(financeiro)

        # Remove o agendamento
        db.session.delete(agendamento)
        db.session.commit()
        flash("Agendamento e registro financeiro excluídos com sucesso.", "success")

    return redirect(url_for("admin.listar_agendamentos"))


# ============================================
# GERENCIAR SERVIÇOS (CRUD)
# ============================================


@admin_bp.route("/servicos", methods=["GET", "POST"])
def listar_servicos():
    """
    Gerencia os serviços (CRUD).
    GET:  Exibe formulário + listagem.
    POST: Adiciona ou edita um serviço.
    """
    check = login_necessario()
    if check:
        return check

    if request.method == "POST":
        nome = request.form["nome"].strip()
        preco = request.form["preco"]
        tempo = request.form["tempo"]
        servico_id = request.form.get("servico_id")

        # Validação básica
        if not nome:
            flash("O nome do serviço é obrigatório.", "error")
            return redirect(url_for("admin.listar_servicos"))

        try:
            preco = int(preco)
            tempo = int(tempo)
        except (ValueError, TypeError):
            flash("Preço e tempo devem ser números válidos.", "error")
            return redirect(url_for("admin.listar_servicos"))

        if preco < 0 or tempo < 1:
            flash("Preço deve ser >= 0 e tempo deve ser >= 1.", "error")
            return redirect(url_for("admin.listar_servicos"))

        if servico_id:
            # EDIÇÃO: atualiza serviço existente
            servico = Servico.query.get(int(servico_id))
            if servico:
                servico.nome = nome
                servico.preco = preco
                servico.tempo = tempo
                db.session.commit()
                flash("Serviço atualizado com sucesso!", "success")
            else:
                flash("Serviço não encontrado.", "error")
        else:
            # CRIAÇÃO: adiciona novo serviço
            if servico_existe_no_banco(nome):
                flash("Já existe um serviço com este nome.", "error")
                return redirect(url_for("admin.listar_servicos"))

            novo_servico = Servico(nome=nome, preco=preco, tempo=tempo)
            db.session.add(novo_servico)
            db.session.commit()
            flash("Serviço adicionado com sucesso!", "success")

        return redirect(url_for("admin.listar_servicos"))

    # GET: exibe a página com listagem
    servicos = Servico.query.all()
    return render_template("admin_servicos.html", servicos=servicos)


@admin_bp.route("/servicos/editar/<int:servico_id>")
def editar_servico(servico_id):
    """
    Exibe o formulário de edição para um serviço específico.
    """
    check = login_necessario()
    if check:
        return check

    servico = Servico.query.get(servico_id)
    if servico is None:
        flash("Serviço não encontrado.", "error")
        return redirect(url_for("admin.listar_servicos"))

    servicos = Servico.query.all()
    return render_template(
        "admin_servicos.html",
        servicos=servicos,
        servico_editar=servico
    )


# ============================================
# FINANCEIRO
# ============================================


@admin_bp.route("/financeiro")
def listar_financeiro():
    """
    Lista todos os registros financeiros.
    Mostra data, cliente, serviço, valor, status e forma de pagamento.
    Exibe totais do dia, mês e ano.
    """
    check = login_necessario()
    if check:
        return check

    from models.financeiro import Financeiro
    from datetime import datetime, date

    hoje = date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")
    mes_atual = hoje.strftime("%Y-%m")
    ano_atual = hoje.strftime("%Y")

    # Busca todos os registros financeiros com dados do agendamento
    registros = db.session.query(
        Financeiro, Agendamento
    ).join(
        Agendamento, Financeiro.agendamento_id == Agendamento.id
    ).order_by(
        Financeiro.criado_em.desc()
    ).all()

    # Calcula totais
    total_dia = 0
    total_mes = 0
    total_ano = 0

    for fin, ag in registros:
        if ag.data == hoje_str:
            total_dia += fin.valor
        if ag.data.startswith(mes_atual):
            total_mes += fin.valor
        if ag.data.startswith(ano_atual):
            total_ano += fin.valor

    return render_template(
        "admin_financeiro.html",
        registros=registros,
        total_dia=total_dia,
        total_mes=total_mes,
        total_ano=total_ano
    )


@admin_bp.route("/financeiro/atualizar_status/<int:financeiro_id>", methods=["POST"])
def atualizar_status_financeiro(financeiro_id):
    """
    Atualiza o status e a forma de pagamento de um registro financeiro.
    """
    check = login_necessario()
    if check:
        return check

    from models.financeiro import Financeiro

    financeiro = Financeiro.query.get(financeiro_id)

    if financeiro is None:
        flash("Registro financeiro não encontrado.", "error")
        return redirect(url_for("admin.listar_financeiro"))

    novo_status = request.form.get("status")
    forma_pagamento = request.form.get("forma_pagamento")

    if novo_status in ["pendente", "pago", "cancelado"]:
        financeiro.status = novo_status

    if forma_pagamento in ["dinheiro", "cartao", "pix", ""]:
        financeiro.forma_pagamento = forma_pagamento if forma_pagamento else None

    db.session.commit()
    flash("Registro financeiro atualizado com sucesso!", "success")
    return redirect(url_for("admin.listar_financeiro"))


@admin_bp.route("/servicos/excluir/<int:servico_id>")
def excluir_servico(servico_id):
    """
    Exclui um serviço pelo ID.
    """
    check = login_necessario()
    if check:
        return check

    servico = Servico.query.get(servico_id)

    if servico is None:
        flash("Serviço não encontrado.", "error")
    else:
        db.session.delete(servico)
        db.session.commit()
        flash("Serviço excluído com sucesso.", "success")

    return redirect(url_for("admin.listar_servicos"))