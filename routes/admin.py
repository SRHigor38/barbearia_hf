# ============================================
# ROTAS ADMINISTRATIVAS
# ============================================
# Rotas protegidas por login. Acessíveis apenas por administradores.

import os
import uuid

from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file,
)
from werkzeug.utils import secure_filename
from models import db
from models.servico import Servico
from models.agendamento import Agendamento
from models.cliente import Cliente
from models.admin import Admin
from models.despesa import Despesa
from models.financeiro import Financeiro
from models.agendamento_servico import AgendamentoServico
from models.plano_tipo_beneficio import PlanoTipoBeneficio
from models.plano_beneficio import PlanoBeneficio
from routes import admin_bp
from utils import normalizar_telefone
from services.barbearia_service import (
    contar_servicos,
    servico_existe_no_banco,
    listar_planos_tipos,
    buscar_plano_tipo_por_id,
    buscar_plano_por_cliente,
    buscar_plano_por_id,
    buscar_cliente_por_telefone,
    criar_plano,
    criar_cliente,
    # Alias obrigatório: a rota abaixo também se chama listar_planos().
    # Sem o alias, listar_planos() dentro do corpo da rota chamaria a
    # própria rota (RecursionError -> HTTP 500 em /admin/planos).
    listar_planos as listar_planos_svc,
    listar_todos_profissionais,
    contar_agendamentos_profissional,
    buscar_profissional_por_id,
    criar_profissional,
    atualizar_profissional,
    excluir_profissional as servico_excluir,
    renovar_plano as renovar_plano_svc,
    cancelar_plano as cancelar_plano_svc,
    devolver_beneficios,
    atualizar_status_plano,
)
from services.financeiro_service import (
    calcular_financeiro, periodo_para_datas, formatar_moeda,
    nome_forma_pagamento, registrar_despesa, atualizar_despesa,
    excluir_despesa, listar_despesas, CATEGORIAS_DESPESA, FORMAS_PAGAMENTO,
    atualizar_pagamento_agendamento, faturamento_planos_periodo,
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
    from models.plano import Plano
    from models.plano_tipo import PlanoTipo
    from models.financeiro import Financeiro

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

    # ============================================
    # INDICADORES DE PLANOS
    # ============================================

    # Quantidade de clientes em planos
    clientes_em_planos = Plano.query.count()

    # Quantidade de planos ativos
    planos_ativos = Plano.query.filter_by(status="ATIVO").count()

    # Quantidade de planos expirados
    planos_expirados = Plano.query.filter_by(status="EXPIRADO").count()

    # Faturamento REAL de planos no mês (vendas + renovações pagas na tabela
    # financeiro). NÃO é a carteira — é o que efetivamente entrou como receita.
    ini_mes, fim_mes = periodo_para_datas("mes")
    faturamento_planos = faturamento_planos_periodo(ini_mes, fim_mes)

    # ============================================
    # FATURAMENTO (FONTE ÚNICA)
    # Usa calcular_financeiro() do financeiro_service para garantir
    # que Dashboard == Financeiro.
    # ============================================
    fin_mes = calcular_financeiro(ini_mes, fim_mes)

    faturamento_mes = fin_mes["receita_bruta"]
    faturamento_hoje = 0
    ini_hoje, fim_hoje = periodo_para_datas("hoje")
    faturamento_hoje = calcular_financeiro(ini_hoje, fim_hoje)["receita_bruta"]

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
        planos_ativos=planos_ativos,
        planos_expirados=planos_expirados,
        clientes_em_planos=clientes_em_planos,
        faturamento_planos=faturamento_planos,
        ultimos_agendamentos=ultimos_agendamentos,
        fin_mes=fin_mes,
    )


# ============================================
# GERENCIAR AGENDAMENTOS
# ============================================


@admin_bp.route("/agendamentos")
def listar_agendamentos():
    """
    Lista todos os agendamentos cadastrados,
    ordenados do mais recente para o mais antigo.
    Suporta filtro por profissional (?profissional_id=) e por telefone
    (?telefone=). O telefone também localiza o cliente cadastrado,
    habilitando a exclusão de todos os dados dele (LGPD) nesta tela.
    """
    check = login_necessario()
    if check:
        return check

    # Filtro por profissional
    filtro_profissional = request.args.get("profissional_id", "")

    # Filtro por telefone (aceita valor formatado: só os dígitos são usados)
    filtro_telefone = request.args.get("telefone", "").strip()
    digitos_telefone = normalizar_telefone(filtro_telefone)

    query = Agendamento.query
    if filtro_profissional.isdigit():
        query = query.filter_by(profissional_id=int(filtro_profissional))
    if digitos_telefone:
        query = query.filter(Agendamento.telefone.like(f"%{digitos_telefone}%"))

    agendamentos = query.order_by(
        Agendamento.data.desc(),
        Agendamento.horario.desc()
    ).all()

    profissionais = listar_todos_profissionais()

    # Cliente cadastrado correspondente ao telefone filtrado: habilita a
    # ação destrutiva "Excluir cliente (LGPD)" na própria lista.
    cliente_lgpd = (
        buscar_cliente_por_telefone(filtro_telefone) if filtro_telefone else None
    )

    return render_template(
        "admin_agendamentos.html",
        agendamentos=agendamentos,
        profissionais=profissionais,
        filtro_profissional=filtro_profissional,
        filtro_telefone=filtro_telefone,
        cliente_lgpd=cliente_lgpd,
        nome_forma_pagamento=nome_forma_pagamento
    )


# ============================================
# EXCLUSÃO DE AGENDAMENTO (LÓGICA REUTILIZÁVEL)
# ============================================


def remover_agendamento_e_dependentes(agendamento):
    """
    Remove um agendamento e tudo que depende dele, SEM commit — a transação
    é fechada por quem chamou (o chamador decide quando commitar):
      - devolve os benefícios do plano (se o agendamento foi feito com plano);
      - remove o registro financeiro associado (mesma regra de sempre);
      - remove o próprio agendamento (AgendamentoServico cai em cascata).

    Reutilizado por excluir_agendamento() e por excluir_cliente_lgpd(),
    para não duplicar a lógica de financeiro/exclusão.
    """
    if agendamento is None:
        return False

    # Se o agendamento usou plano, devolve os benefícios consumidos
    # (somente finitos; ilimitados nunca foram decrementados).
    if agendamento.plano_id:
        if agendamento.servicos_relacionados:
            servico_ids = [r.servico_id for r in agendamento.servicos_relacionados]
            devolver_beneficios(agendamento.plano_id, servico_ids, commit=False)

    # Remove o registro financeiro associado (se existir)
    financeiro = Financeiro.query.filter_by(agendamento_id=agendamento.id).first()
    if financeiro:
        db.session.delete(financeiro)

    # Remove o agendamento
    db.session.delete(agendamento)
    return True


@admin_bp.route("/agendamentos/excluir/<int:agendamento_id>", methods=["POST"])
def excluir_agendamento(agendamento_id):
    """
    Exclui um agendamento pelo ID.
    - Devolve benefícios do plano (se agendamento com plano).
    - Remove o registro financeiro associado.
    POST + CSRF: mutação nunca via GET.
    """
    check = login_necessario()
    if check:
        return check

    agendamento = Agendamento.query.get(agendamento_id)

    if agendamento is None:
        flash("Agendamento não encontrado.", "error")
    else:
        remover_agendamento_e_dependentes(agendamento)
        db.session.commit()
        flash("Agendamento e registro financeiro excluídos com sucesso.", "success")

    return redirect(url_for("admin.listar_agendamentos"))


# ============================================
# LGPD — EXCLUSÃO DOS DADOS DE UM CLIENTE
# ============================================
# Direito de eliminação dos dados pessoais (Lei 13.709/2018, art. 18, VI):
# apaga o Cliente e TODOS os dados ligados a ele (agendamentos, financeiro,
# plano, benefícios e histórico de renovação) em UMA única transação.


@admin_bp.route("/clientes/excluir/<int:cliente_id>", methods=["POST"])
def excluir_cliente_lgpd(cliente_id):
    """
    Exclui um cliente e todos os dados vinculados a ele (LGPD).

    Ordem obrigatória (integridade referencial):
      1. Agendamentos do cliente (cliente_id) e os agendamentos do plano
         (plano_id), reaproveitando remover_agendamento_e_dependentes():
         devolve benefícios, apaga o financeiro do agendamento e o agendamento.
      2. Plano do cliente + o financeiro de venda/renovação ligado a ele
         (os PlanoBeneficio caem em cascata pelo relacionamento existente).
      3. O próprio registro Cliente.

    Commit SOMENTE no final: qualquer erro no meio faz rollback e nada é
    removido. POST + CSRF: mutação nunca via GET.
    """
    check = login_necessario()
    if check:
        return check

    cliente = Cliente.query.get(cliente_id)
    if cliente is None:
        flash("Cliente não encontrado.", "error")
        return redirect(url_for("admin.listar_agendamentos"))

    agendamentos_removidos = 0
    planos_removidos = 0

    try:
        plano = buscar_plano_por_cliente(cliente.id)

        # 1) Agendamentos do cliente (cliente_id)
        agendamentos = Agendamento.query.filter_by(cliente_id=cliente.id).all()

        # ... e os agendamentos ligados ao plano do cliente
        # (agendamento.plano_id -> plano.id precisa sair antes do plano,
        # senão o PostgreSQL recusaria a exclusão do plano).
        if plano is not None:
            ids_coletados = {agendamento.id for agendamento in agendamentos}
            for agendamento in Agendamento.query.filter_by(plano_id=plano.id).all():
                if agendamento.id not in ids_coletados:
                    agendamentos.append(agendamento)
                    ids_coletados.add(agendamento.id)

        for agendamento in agendamentos:
            remover_agendamento_e_dependentes(agendamento)
            agendamentos_removidos += 1

        # 2) Plano do cliente (venda + histórico de renovação no financeiro)
        if plano is not None:
            for financeiro in Financeiro.query.filter_by(plano_id=plano.id).all():
                db.session.delete(financeiro)
            db.session.delete(plano)
            planos_removidos = 1

        # 3) Cliente
        db.session.delete(cliente)

        # Commit único: tudo ou nada
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Falha ao excluir os dados do cliente (LGPD) id=%s", cliente_id
        )
        flash(
            "Não foi possível excluir os dados do cliente. Nada foi removido.",
            "error",
        )
        return redirect(url_for("admin.listar_agendamentos"))

    flash(
        "Dados do cliente excluídos (LGPD): "
        f"{agendamentos_removidos} agendamento(s) e {planos_removidos} plano(s) "
        "removido(s), junto com o financeiro relacionado.",
        "success",
    )
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
        try:
            nome = request.form.get("nome", "").strip()
            preco = request.form.get("preco", "")
            tempo = request.form.get("tempo", "")
        except Exception:
            flash("Dados inválidos.", "error")
            return redirect(url_for("admin.listar_servicos"))
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
# GERENCIAMENTO DE PROFISSIONAIS
# ============================================

# Extensões permitidas para upload de foto
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2MB


def extensao_permitida(nome_arquivo):
    """Verifica se a extensão do arquivo é permitida."""
    return "." in nome_arquivo and nome_arquivo.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def salvar_foto_profissional(arquivo):
    """
    Valida e salva a foto do profissional de forma segura.
    Retorna o nome do arquivo salvo ou None se inválido/ausente.
    """
    if not arquivo or arquivo.filename == "":
        return None

    nome_limpo = secure_filename(arquivo.filename)

    # Valida extensão
    if not extensao_permitida(nome_limpo):
        flash("Formato de imagem não permitido (use png, jpg, jpeg, gif, webp).", "error")
        return None

    # Valida assinatura real do arquivo (magic bytes) — não confia só na extensão.
    # Lê os primeiros bytes e depois volta o cursor para salvar o arquivo completo.
    try:
        cabecalho = arquivo.read(12)
        arquivo.seek(0)
    except Exception:
        flash("Não foi possível ler a imagem enviada.", "error")
        return None

    assinaturas_validas = (
        b"\x89PNG",          # PNG
        b"\xff\xd8\xff",     # JPEG
        b"GIF87a", b"GIF89a",  # GIF
        b"RIFF",             # WEBP (RIFF....WEBP)
    )
    eh_imagem = cabecalho.startswith(assinaturas_validas)
    eh_webp = cabecalho.startswith(b"RIFF") and b"WEBP" in cabecalho
    if not (eh_imagem and (not cabecalho.startswith(b"RIFF") or eh_webp)):
        flash("Arquivo inválido: o conteúdo não corresponde a uma imagem.", "error")
        return None

    # Gera nome seguro e único para evitar sobrescrita
    ext = nome_limpo.rsplit(".", 1)[1].lower()
    nome_arquivo = f"profissional_{uuid.uuid4().hex}.{ext}"

    # Cria diretório se não existir
    pasta = os.path.join(current_app.root_path, "static", "imagens")
    os.makedirs(pasta, exist_ok=True)

    # Salva o arquivo (MAX_CONTENT_LENGTH no config já limita a 2MB)
    arquivo.save(os.path.join(pasta, nome_arquivo))
    return nome_arquivo


@admin_bp.route("/profissionais")
def listar_profissionais():
    """
    Lista todos os profissionais (ativos e inativos).
    """
    check = login_necessario()
    if check:
        return check

    profissionais = listar_todos_profissionais()
    # Adiciona quantidade de agendamentos para cada profissional
    for prof in profissionais:
        prof.qtd_agendamentos = contar_agendamentos_profissional(prof.id)

    return render_template("admin_profissionais.html", profissionais=profissionais)


@admin_bp.route("/profissionais/novo", methods=["GET", "POST"])
def novo_profissional():
    """
    Cadastra um novo profissional (com upload de foto).
    Campos: foto, nome e status (ativo).
    """
    check = login_necessario()
    if check:
        return check

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()

        if not nome:
            flash("O nome do profissional é obrigatório.", "error")
        else:
            foto = salvar_foto_profissional(request.files.get("foto"))

            criar_profissional(nome=nome, foto=foto)
            flash("Profissional cadastrado com sucesso!", "success")
            return redirect(url_for("admin.listar_profissionais"))

    return render_template("admin_profissional_form.html")


@admin_bp.route("/profissionais/editar/<int:profissional_id>", methods=["GET", "POST"])
def editar_profissional(profissional_id):
    """
    Edita um profissional (com troca de foto).
    """
    check = login_necessario()
    if check:
        return check

    profissional = buscar_profissional_por_id(profissional_id)
    if profissional is None:
        flash("Profissional não encontrado.", "error")
        return redirect(url_for("admin.listar_profissionais"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        ativo = request.form.get("ativo") == "on"

        if not nome:
            flash("O nome do profissional é obrigatório.", "error")
        else:
            # Troca de foto (se enviada)
            nova_foto = salvar_foto_profissional(request.files.get("foto"))
            if nova_foto:
                # Remove foto antiga se existir
                if profissional.foto:
                    caminho = os.path.join(current_app.root_path, "static", "imagens", profissional.foto)
                    if os.path.exists(caminho):
                        os.remove(caminho)
                foto = nova_foto
            else:
                foto = profissional.foto

            atualizar_profissional(
                profissional_id,
                nome=nome,
                foto=foto,
                ativo=ativo,
            )
            flash("Profissional atualizado com sucesso!", "success")
            return redirect(url_for("admin.listar_profissionais"))

    return render_template("admin_profissional_form.html", profissional=profissional)


@admin_bp.route("/profissionais/alternar/<int:profissional_id>", methods=["POST"])
def alternar_profissional(profissional_id):
    """
    Ativa ou desativa um profissional.
    POST + CSRF: mutação nunca via GET (evita CSRF/logout-forçado por link).
    """
    check = login_necessario()
    if check:
        return check

    profissional = buscar_profissional_por_id(profissional_id)
    if profissional is None:
        flash("Profissional não encontrado.", "error")
    else:
        novo_status = not profissional.ativo
        atualizar_profissional(profissional_id, ativo=novo_status)
        status_texto = "ativado" if novo_status else "desativado"
        flash(f"Profissional {status_texto} com sucesso!", "success")

    return redirect(url_for("admin.listar_profissionais"))


@admin_bp.route("/profissionais/excluir/<int:profissional_id>", methods=["POST"])
def excluir_profissional(profissional_id):
    """
    Exclui um profissional somente se for seguro (sem agendamentos).
    POST + CSRF: mutação nunca via GET.
    """
    check = login_necessario()
    if check:
        return check

    if servico_excluir(profissional_id):
        flash("Profissional excluído com sucesso!", "success")
    else:
        flash("Não é possível excluir: o profissional possui agendamentos. Desative-o em vez disso.", "error")

    return redirect(url_for("admin.listar_profissionais"))


# ============================================
# GERENCIAMENTO DE PLANOS MENSAIS
# ============================================


@admin_bp.route("/planos")
def listar_planos():
    """
    Lista todos os planos cadastrados.
    """
    check = login_necessario()
    if check:
        return check

    planos = listar_planos_svc()

    # Atualiza status real (expirado/esgotado) para cada plano
    for plano in planos:
        atualizar_status_plano(plano)

    return render_template("admin_planos.html", planos=planos)


@admin_bp.route("/planos/novo", methods=["GET", "POST"])
def novo_plano():
    """
    Cadastra um cliente em um plano mensal.
    O admin seleciona o tipo de plano (Bronze, Prata, etc.) e o cliente.
    Os benefícios, preço e dias são carregados automaticamente do plano tipo.
    """
    check = login_necessario()
    if check:
        return check

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()
        plano_tipo_id = request.form.get("plano_tipo_id", "")
        diasSelecionados = request.form.getlist("dias")  # lista dos dias selecionados

        if not nome or not telefone:
            flash("Nome e telefone são obrigatórios.", "error")
        elif not plano_tipo_id or not plano_tipo_id.isdigit():
            flash("Selecione um tipo de plano.", "error")
        else:
            # Valida o tipo de plano ANTES de criar o cliente (evita cliente órfão)
            if buscar_plano_tipo_por_id(int(plano_tipo_id)) is None:
                flash("Tipo de plano inválido.", "error")
            else:
                # Forma de pagamento da venda do plano (valores em REAIS)
                forma_pagamento = request.form.get("forma_pagamento", "dinheiro")
                taxa_cartao = request.form.get("taxa_cartao", "0")

                # Cria ou reutiliza o cliente
                cliente = criar_cliente(nome=nome, telefone=telefone)

                # Verifica se cliente já possui plano
                if buscar_plano_por_cliente(cliente.id) is not None:
                    flash("Este cliente já possui um plano.", "error")
                else:
                    # Dias permitidos: se nenhum marcado, usa os do plano tipo
                    dias = ",".join(diasSelecionados) if diasSelecionados else None

                    # Cria o plano a partir do tipo pré-definido + lançamento financeiro
                    # (agendamento_id = NULL, plano_id preenchido, valor em REAIS)
                    plano = criar_plano(
                        cliente_id=cliente.id,
                        plano_tipo_id=int(plano_tipo_id),
                        dias_permitidos=dias,
                        forma_pagamento=forma_pagamento,
                        taxa_cartao=taxa_cartao,
                    )
                    if plano is None:
                        flash(
                            "Não foi possível criar o plano. Nenhum dado foi salvo.",
                            "error"
                        )
                    else:
                        flash(
                            f"Plano {plano.nome} criado com sucesso! "
                            f"Valor: {formatar_moeda(plano.preco)} — "
                            f"Código de acesso: {plano.codigo_acesso}",
                            "success"
                        )
                        return redirect(url_for("admin.listar_planos"))

    # GET: exibe o formulário com os planos tipos
    planos_tipos = listar_planos_tipos()
    return render_template("admin_plano_form.html", planos_tipos=planos_tipos)


@admin_bp.route("/planos/renovar/<int:plano_id>", methods=["POST"])
def renovar_plano(plano_id):
    """
    Renova um plano: restaura cortes e nova validade de 30 dias.
    """
    check = login_necessario()
    if check:
        return check

    forma_pagamento = request.form.get("forma_pagamento", "dinheiro")
    taxa_cartao = request.form.get("taxa_cartao", "0")

    plano = renovar_plano_svc(
        plano_id, forma_pagamento=forma_pagamento, taxa_cartao=taxa_cartao
    )
    if plano is None:
        flash("Não foi possível renovar o plano.", "error")
    else:
        flash(
            f"Plano {plano.nome} renovado com sucesso! "
            f"Valor: {formatar_moeda(plano.preco)} — nova validade {plano.data_validade}.",
            "success"
        )
    return redirect(url_for("admin.listar_planos"))


@admin_bp.route("/planos/cancelar/<int:plano_id>", methods=["POST"])
def cancelar_plano(plano_id):
    """
    Cancela um plano (status CANCELADO).
    """
    check = login_necessario()
    if check:
        return check

    cancelar_plano_svc(plano_id)
    flash("Plano cancelado.", "success")
    return redirect(url_for("admin.listar_planos"))


@admin_bp.route("/planos/codigo/<int:plano_id>")
def ver_codigo_plano(plano_id):
    """
    Exibe o código de acesso de um plano (apenas admin autenticado).
    """
    check = login_necessario()
    if check:
        return check

    plano = buscar_plano_por_id(plano_id)
    if plano is None:
        flash("Plano não encontrado.", "error")
        return redirect(url_for("admin.listar_planos"))

    flash(f"Código de acesso de {plano.cliente.nome}: {plano.codigo_acesso}", "info")
    return redirect(url_for("admin.listar_planos"))


@admin_bp.route("/servicos/excluir/<int:servico_id>", methods=["POST"])
def excluir_servico(servico_id):
    """
    Exclui um serviço pelo ID.
    POST + CSRF: mutação nunca via GET.
    """
    check = login_necessario()
    if check:
        return check

    servico = Servico.query.get(servico_id)

    if servico is None:
        flash("Serviço não encontrado.", "error")
    else:
        # Proteção de integridade: não excluir serviço em uso
        # (agendamentos, pacotes de agendamento, catálogo de planos ou
        # benefícios de clientes). Excluir quebraria histórico e planos.
        em_uso = (
            Agendamento.query.filter_by(servico=servico.nome).first() is not None
            or AgendamentoServico.query.filter_by(servico_id=servico.id).first() is not None
            or PlanoTipoBeneficio.query.filter_by(servico_id=servico.id).first() is not None
            or PlanoBeneficio.query.filter_by(servico_id=servico.id).first() is not None
        )
        if em_uso:
            flash(
                "Não é possível excluir: este serviço está em uso "
                "(agendamentos ou planos).",
                "error",
            )
        else:
            db.session.delete(servico)
            db.session.commit()
            flash("Serviço excluído com sucesso.", "success")

    return redirect(url_for("admin.listar_servicos"))
# ============================================
# REGISTRAR / ALTERAR PAGAMENTO DE AGENDAMENTO
# ============================================


@admin_bp.route("/agendamentos/pagamento/<int:agendamento_id>", methods=["GET", "POST"])
def pagamento_agendamento(agendamento_id):
    """
    Registra ou altera o pagamento de um agendamento.
    Permite escolher forma, status e taxa de cartão.
    Somente status "pago" entra no faturamento.
    """
    check = login_necessario()
    if check:
        return check

    agendamento = Agendamento.query.get(agendamento_id)
    if agendamento is None:
        flash("Agendamento não encontrado.", "error")
        return redirect(url_for("admin.listar_agendamentos"))

    financeiro = Financeiro.query.filter_by(agendamento_id=agendamento.id).first()

    from models.servico import Servico
    servico_obj = Servico.query.filter_by(nome=agendamento.servico).first()
    valor_default = float(servico_obj.preco) if servico_obj else 0

    if request.method == "POST":
        status = request.form.get("status", "pendente")
        forma = request.form.get("forma_pagamento", "")
        taxa = request.form.get("taxa_cartao", "0")
        valor = request.form.get("valor", str(valor_default))

        try:
            valor_float = round(float(valor or 0), 2)
        except (TypeError, ValueError):
            flash("Valor inválido.", "error")
            return redirect(
                url_for("admin.pagamento_agendamento", agendamento_id=agendamento.id)
            )
        if valor_float < 0:
            flash("Valor não pode ser negativo.", "error")
            return redirect(
                url_for("admin.pagamento_agendamento", agendamento_id=agendamento.id)
            )

        if financeiro is None:
            financeiro = Financeiro(agendamento_id=agendamento.id)
            db.session.add(financeiro)
            db.session.flush()

        resultado, erro = atualizar_pagamento_agendamento(
            agendamento.id, status, forma, taxa_cartao=taxa
        )
        if erro:
            db.session.rollback()
            flash(erro, "error")
        else:
            # Atualiza o valor cobrado (receita bruta) após validar status/forma.
            # atualizar_pagamento_agendamento já normalizou taxa_cartao e
            # zerou a taxa ao trocar cartão -> PIX/dinheiro.
            financeiro = Financeiro.query.filter_by(
                agendamento_id=agendamento.id
            ).first()
            if financeiro is not None:
                financeiro.valor = valor_float
                db.session.commit()
            flash("Pagamento registrado com sucesso.", "success")
        return redirect(url_for("admin.listar_agendamentos"))

    return render_template(
        "admin_pagamento.html",
        agendamento=agendamento,
        financeiro=financeiro,
        valor_default=valor_default,
        formas_pagamento=FORMAS_PAGAMENTO,
    )


# ============================================
# PÁGINA FINANCEIRA (PAINEL FINANCEIRO)
# ============================================


@admin_bp.route("/financeiro")
def financeiro():
    """Painel financeiro: cards, filtro por período e lista de movimentações."""
    check = login_necessario()
    if check:
        return check

    periodo = request.args.get("periodo", "mes")
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")

    ini, fim = periodo_para_datas(periodo, data_inicio, data_fim)
    if data_inicio and data_fim and data_inicio > data_fim:
        flash("Data inicial não pode ser maior que a data final.", "error")
        ini, fim = periodo_para_datas("mes")

    indicadores = calcular_financeiro(ini, fim)

    return render_template(
        "admin_financeiro.html",
        indicadores=indicadores,
        periodo=periodo,
        data_inicio=ini,
        data_fim=fim,
        formatar_moeda=formatar_moeda,
        nome_forma_pagamento=nome_forma_pagamento,
    )

@admin_bp.route("/financeiro/pdf")
def financeiro_pdf():
    """Gera o relatório financeiro em PDF do período selecionado."""
    check = login_necessario()
    if check:
        return check

    from services.pdf_service import gerar_relatorio_pdf

    periodo = request.args.get("periodo", "mes")
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")

    ini, fim = periodo_para_datas(periodo, data_inicio, data_fim)
    if data_inicio and data_fim and data_inicio > data_fim:
        flash("Data inicial não pode ser maior que a data final.", "error")
        ini, fim = periodo_para_datas("mes")

    indicadores = calcular_financeiro(ini, fim)
    pdf_buffer = gerar_relatorio_pdf(ini, fim, indicadores, indicadores["movimentacoes"])

    nome_arquivo = f"relatorio_financeiro_{ini}_a_{fim}.pdf"
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nome_arquivo,
    )


# ============================================
# DESPESAS / GASTOS (CRUD)
# ============================================


@admin_bp.route("/gastos", methods=["GET", "POST"])
def listar_gastos():
    """Lista gastos com filtro por período e categoria. Formulário de novo gasto."""
    check = login_necessario()
    if check:
        return check

    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    categoria = request.args.get("categoria", "")

    if request.method == "POST":
        descricao = request.form.get("descricao", "")
        cat = request.form.get("categoria", "Outros")
        valor = request.form.get("valor", "")
        data = request.form.get("data", "")
        observacao = request.form.get("observacao", "")

        despesa, erro = registrar_despesa(descricao, cat, valor, data, observacao)
        if erro:
            flash(erro, "error")
        else:
            flash("Gasto cadastrado com sucesso.", "success")
        return redirect(url_for("admin.listar_gastos"))

    despesas = listar_despesas(data_inicio, data_fim, categoria)
    return render_template(
        "admin_gastos.html",
        despesas=despesas,
        categorias=CATEGORIAS_DESPESA,
        data_inicio=data_inicio,
        data_fim=data_fim,
        categoria_filtro=categoria,
        formatar_moeda=formatar_moeda,
    )

@admin_bp.route("/gastos/editar/<int:despesa_id>", methods=["GET", "POST"])
def editar_gasto(despesa_id):
    """Edita um gasto existente."""
    check = login_necessario()
    if check:
        return check

    despesa = Despesa.query.get(despesa_id)
    if despesa is None:
        flash("Gasto não encontrado.", "error")
        return redirect(url_for("admin.listar_gastos"))

    if request.method == "POST":
        descricao = request.form.get("descricao", "")
        cat = request.form.get("categoria", "Outros")
        valor = request.form.get("valor", "")
        data = request.form.get("data", "")
        observacao = request.form.get("observacao", "")

        ok, erro = atualizar_despesa(despesa_id, descricao, cat, valor, data, observacao)
        if erro:
            flash(erro, "error")
        else:
            flash("Gasto atualizado com sucesso.", "success")
        return redirect(url_for("admin.listar_gastos"))

    return render_template(
        "admin_gasto_form.html",
        despesa=despesa,
        categorias=CATEGORIAS_DESPESA,
    )


@admin_bp.route("/gastos/excluir/<int:despesa_id>", methods=["POST"])
def excluir_gasto(despesa_id):
    """Exclui um gasto."""
    check = login_necessario()
    if check:
        return check

    if excluir_despesa(despesa_id):
        flash("Gasto excluído com sucesso.", "success")
    else:
        flash("Gasto não encontrado.", "error")
    return redirect(url_for("admin.listar_gastos"))

# ============================================
# RELATÓRIO FINANCEIRO (na área de relatórios)
# ============================================


@admin_bp.route("/relatorios/financeiro")
def relatorio_financeiro():
    """Relatório financeiro com resumo + detalhamento de receitas e despesas."""
    check = login_necessario()
    if check:
        return check

    periodo = request.args.get("periodo", "mes")
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")

    ini, fim = periodo_para_datas(periodo, data_inicio, data_fim)
    if data_inicio and data_fim and data_inicio > data_fim:
        flash("Data inicial não pode ser maior que a data final.", "error")
        ini, fim = periodo_para_datas("mes")

    indicadores = calcular_financeiro(ini, fim)
    return render_template(
        "admin_relatorio_financeiro.html",
        indicadores=indicadores,
        data_inicio=ini,
        data_fim=fim,
        periodo=periodo,
        formatar_moeda=formatar_moeda,
        nome_forma_pagamento=nome_forma_pagamento,
    )


# ============================================
# CONFIGURAÇÕES DO ADMINISTRADOR
# ============================================


@admin_bp.route("/config", methods=["GET", "POST"])
def configuracoes():
    """Página de configurações do administrador (alterar usuário e senha)."""
    check = login_necessario()
    if check:
        return check

    admin_id = session.get("admin_id")
    admin = Admin.query.get(admin_id)
    if admin is None:
        flash("Administrador não encontrado.", "error")
        return redirect(url_for("admin.logout"))

    if request.method == "POST":
        acao = request.form.get("acao", "")

        if acao == "usuario":
            novo_usuario = request.form.get("novo_usuario", "").strip()

            if not novo_usuario:
                flash("O novo usuário é obrigatório.", "error")
            elif len(novo_usuario) < 3:
                flash("O usuário deve ter no mínimo 3 caracteres.", "error")
            elif Admin.query.filter(
                Admin.usuario == novo_usuario, Admin.id != admin.id
            ).first():
                flash("Este usuário já está em uso.", "error")
            else:
                admin.usuario = novo_usuario
                db.session.commit()
                session["admin_usuario"] = novo_usuario
                flash("Usuário alterado com sucesso.", "success")

        elif acao == "senha":
            senha_atual = request.form.get("senha_atual", "")
            nova_senha = request.form.get("nova_senha", "")
            confirmar = request.form.get("confirmar_senha", "")

            bcrypt = current_app.bcrypt
            if not bcrypt.check_password_hash(admin.senha_hash, senha_atual):
                flash("Senha atual incorreta.", "error")
            elif len(nova_senha) < 6:
                flash("A nova senha deve ter no mínimo 6 caracteres.", "error")
            elif nova_senha != confirmar:
                flash("A confirmação não confere com a nova senha.", "error")
            else:
                admin.senha_hash = bcrypt.generate_password_hash(nova_senha).decode("utf-8")
                db.session.commit()
                flash("Senha alterada com sucesso.", "success")

        return redirect(url_for("admin.configuracoes"))

    return render_template("admin_config.html")