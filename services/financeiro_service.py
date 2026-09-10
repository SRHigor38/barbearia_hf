# ============================================
# SERVIÇO: Lógica Financeira
# ============================================
# Centraliza TODO o cálculo financeiro da HF Barbearia.
# Fonte única usada por: Dashboard, Página Financeiro,
# Relatórios e Exportação PDF.
#
# UNIDADES:
#   financeiro.valor       -> REAIS (Float)
#   financeiro.taxa_cartao -> REAIS (Float)
#   despesa.valor          -> REAIS (Float)
#   plano_tipo.preco       -> CENTAVOS (Integer; 9000 = R$ 90,00)
#
# LUCRO LÍQUIDO = RECEITA BRUTA - DESPESAS(GASTOS + TAXAS)
# Somente financeiro.status == "pago" entra na receita.

from datetime import datetime, date, timedelta
from models import db
from models.financeiro import Financeiro
from models.despesa import Despesa

CATEGORIAS_DESPESA = [
    "Produtos", "Materiais", "Aluguel", "Energia", "Água", "Internet",
    "Equipamentos", "Manutenção", "Marketing", "Taxas", "Outros",
]

FORMAS_PAGAMENTO = ["dinheiro", "pix", "cartao"]


# ============================================
# FORMATAÇÃO E CONVERSÃO
# ============================================


def formatar_moeda(valor):
    """Formata um valor numérico como moeda brasileira (R$ 0,00)."""
    try:
        valor = float(valor or 0)
    except (TypeError, ValueError):
        valor = 0.0
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def preco_plano_reais(plano_tipo):
    """Converte preço do plano (centavos) para reais. 9000 -> 90.0"""
    if plano_tipo is None:
        return 0.0
    try:
        return float(plano_tipo.preco) / 100.0
    except (TypeError, ValueError):
        return 0.0


def nome_forma_pagamento(forma):
    nomes = {"dinheiro": "Dinheiro", "pix": "PIX", "cartao": "Cartão"}
    return nomes.get(forma, forma or "—")


# ============================================
# DESPESAS (CRUD)
# ============================================


def registrar_despesa(descricao, categoria, valor, data, observacao=None):
    """
    Cria um gasto manual da barbearia.
    Validações: descrição obrigatória, valor > 0, data obrigatória.
    Retorna (despesa, None) ou (None, mensagem_erro).
    """
    descricao = (descricao or "").strip()
    categoria = (categoria or "Outros").strip()
    observacao = (observacao or "").strip() or None

    if not descricao:
        return None, "A descrição do gasto é obrigatória."
    if not data:
        return None, "A data do gasto é obrigatória."
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return None, "Valor inválido."
    if valor <= 0:
        return None, "O valor do gasto deve ser maior que zero."

    despesa = Despesa(
        descricao=descricao,
        categoria=categoria,
        valor=round(valor, 2),
        data=data,
        observacao=observacao,
    )
    db.session.add(despesa)
    db.session.commit()
    return despesa, None


def atualizar_despesa(despesa_id, descricao, categoria, valor, data, observacao=None):
    """Atualiza um gasto existente. Retorna (True, None) ou (False, erro)."""
    despesa = Despesa.query.get(despesa_id)
    if despesa is None:
        return False, "Gasto não encontrado."

    descricao = (descricao or "").strip()
    categoria = (categoria or "Outros").strip()

    if not descricao:
        return False, "A descrição do gasto é obrigatória."
    if not data:
        return False, "A data do gasto é obrigatória."
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return False, "Valor inválido."
    if valor <= 0:
        return False, "O valor do gasto deve ser maior que zero."

    despesa.descricao = descricao
    despesa.categoria = categoria
    despesa.valor = round(valor, 2)
    despesa.data = data
    despesa.observacao = (observacao or "").strip() or None
    db.session.commit()
    return True, None


def excluir_despesa(despesa_id):
    """Exclui um gasto pelo ID. Retorna True se excluído."""
    despesa = Despesa.query.get(despesa_id)
    if despesa is None:
        return False
    db.session.delete(despesa)
    db.session.commit()
    return True


def listar_despesas(data_inicio=None, data_fim=None, categoria=None):
    """Lista despesas, opcionalmente filtrando por período e categoria."""
    query = Despesa.query
    if data_inicio:
        query = query.filter(Despesa.data >= data_inicio)
    if data_fim:
        query = query.filter(Despesa.data <= data_fim)
    if categoria:
        query = query.filter(Despesa.categoria == categoria)
    return query.order_by(Despesa.data.desc(), Despesa.id.desc()).all()
# ============================================
# PAGAMENTOS DE AGENDAMENTO
# ============================================


def atualizar_pagamento_agendamento(agendamento_id, status, forma_pagamento,
                                    taxa_cartao=None):
    """
    Atualiza o pagamento de um agendamento (cria ou edita o Financeiro).
    Regras:
      - Se forma == cartao, usa a taxa informada (>= 0).
      - Se mudar para dinheiro/pix, ZERA a taxa (evita dupla contagem).
      - Status "pago" é o único que entra no faturamento.
    Retorna (financeiro, None) ou (None, mensagem_erro).
    """
    if status not in ("pendente", "pago", "cancelado"):
        return None, "Status de pagamento inválido."

    forma = (forma_pagamento or "").strip() or None
    if status == "pago" and forma not in FORMAS_PAGAMENTO:
        return None, "Informe a forma de pagamento para marcar como pago."
    if forma and forma not in FORMAS_PAGAMENTO:
        return None, "Forma de pagamento inválida."

    financeiro = Financeiro.query.filter_by(agendamento_id=agendamento_id).first()

    if financeiro is None:
        financeiro = Financeiro(agendamento_id=agendamento_id)
        db.session.add(financeiro)

    # Taxa: somente cartão
    if forma == "cartao":
        try:
            taxa = float(taxa_cartao or 0)
        except (TypeError, ValueError):
            taxa = 0.0
        if taxa < 0:
            return None, "A taxa da maquininha não pode ser negativa."
        financeiro.taxa_cartao = round(taxa, 2)
    else:
        # Dinheiro/PIX: zera a taxa anterior (sem duplicar despesa)
        financeiro.taxa_cartao = 0.0

    financeiro.status = status
    financeiro.forma_pagamento = forma if status != "pendente" else None
    if not financeiro.tipo:
        financeiro.tipo = "agendamento"
    if not financeiro.data_pagamento:
        if financeiro.agendamento and financeiro.agendamento.data:
            financeiro.data_pagamento = financeiro.agendamento.data
        else:
            financeiro.data_pagamento = date.today().strftime("%Y-%m-%d")

    db.session.commit()
    return financeiro, None
# ============================================
# CÁLCULO FINANCEIRO CENTRAL (FONTE ÚNICA)
# ============================================


def _filtrar_financeiro(data_inicio=None, data_fim=None, status="pago"):
    """Busca financeiros pagos no período usando data_pagamento (fallback criado_em)."""
    query = Financeiro.query
    if status:
        query = query.filter(Financeiro.status == status)

    registros = query.all()
    resultado = []
    for reg in registros:
        data_reg = None
        if reg.data_pagamento:
            data_reg = reg.data_pagamento
        elif reg.criado_em:
            data_reg = reg.criado_em.strftime("%Y-%m-%d")
        else:
            data_reg = datetime.now().strftime("%Y-%m-%d")

        if data_inicio and data_reg < data_inicio:
            continue
        if data_fim and data_reg > data_fim:
            continue
        resultado.append((reg, data_reg))
    return resultado


def _descricao_auto(reg):
    """Gera uma descrição legível para um financeiro sem descrição explícita."""
    if reg.tipo == "plano":
        return f"Venda de plano #{reg.plano_id}"
    if reg.tipo == "renovacao_plano":
        return f"Renovação de plano #{reg.plano_id}"
    if reg.agendamento and reg.agendamento.servico:
        return f"{reg.agendamento.servico} - {reg.agendamento.nome}"
    return f"Serviço #{reg.agendamento_id}"


def calcular_financeiro(data_inicio=None, data_fim=None):
    """
    Calcula os indicadores financeiros de um período.
    Retorna dict com: receita_bruta, despesas_gastos, despesas_taxas,
    despesas_total, lucro_liquido, quantidade_receitas, quantidade_despesas,
    movimentacoes (mais recentes primeiro).
    """
    receitas_bruta = 0.0
    soma_taxas = 0.0
    receitas_lista = []
    for reg, data_reg in _filtrar_financeiro(data_inicio, data_fim, status="pago"):
        receitas_bruta += reg.valor or 0
        if reg.taxa_cartao and reg.taxa_cartao > 0:
            soma_taxas += float(reg.taxa_cartao)
        receitas_lista.append({
            "data": data_reg,
            "tipo": "receita",
            "descricao": reg.descricao or _descricao_auto(reg),
            "origem": reg.tipo or "agendamento",
            "forma_pagamento": reg.forma_pagamento,
            "valor": float(reg.valor or 0),
            "referencia_id": reg.agendamento_id or reg.plano_id,
            "taxa_cartao": float(reg.taxa_cartao or 0),
        })

    gastos_lista = []
    soma_gastos = 0.0
    for desp in listar_despesas(data_inicio, data_fim):
        soma_gastos += desp.valor or 0
        gastos_lista.append({
            "data": desp.data,
            "tipo": "despesa",
            "descricao": desp.descricao,
            "origem": desp.categoria or "Outros",
            "forma_pagamento": None,
            "valor": float(desp.valor or 0),
            "referencia_id": desp.id,
            "taxa_cartao": 0,
        })

    despesas_taxas = soma_taxas
    despesas_total = soma_gastos + soma_taxas
    lucro_liquido = receitas_bruta - despesas_total

    movimentacoes = sorted(
        receitas_lista + gastos_lista,
        key=lambda m: m["data"],
        reverse=True
    )

    return {
        "receita_bruta": round(receitas_bruta, 2),
        "despesas_gastos": round(soma_gastos, 2),
        "despesas_taxas": round(despesas_taxas, 2),
        "despesas_total": round(despesas_total, 2),
        "lucro_liquido": round(lucro_liquido, 2),
        "quantidade_receitas": len(receitas_lista),
        "quantidade_despesas": len(gastos_lista),
        "movimentacoes": movimentacoes,
    }


# ============================================
# AUXILIARES DE PERÍODO
# ============================================


def periodo_para_datas(periodo, data_inicio=None, data_fim=None):
    """
    Normaliza um filtro de período em (data_inicio, data_fim).
    periodos: hoje | semana | mes | mes_passado | personalizado
    """
    hoje = date.today()

    if periodo == "hoje":
        return hoje.strftime("%Y-%m-%d"), hoje.strftime("%Y-%m-%d")

    if periodo == "semana":
        inicio = hoje - timedelta(days=hoje.weekday())
        return inicio.strftime("%Y-%m-%d"), hoje.strftime("%Y-%m-%d")

    if periodo == "mes":
        inicio = hoje.replace(day=1)
        return inicio.strftime("%Y-%m-%d"), hoje.strftime("%Y-%m-%d")

    if periodo == "mes_passado":
        primeiro_mes = hoje.replace(day=1)
        fim_mes_passado = primeiro_mes - timedelta(days=1)
        inicio_mes_passado = fim_mes_passado.replace(day=1)
        return (
            inicio_mes_passado.strftime("%Y-%m-%d"),
            fim_mes_passado.strftime("%Y-%m-%d"),
        )

    # personalizado
    if not data_inicio or not data_fim:
        inicio = hoje.replace(day=1)
        return inicio.strftime("%Y-%m-%d"), hoje.strftime("%Y-%m-%d")
    return data_inicio, data_fim
# ============================================
# MIGRAÇÃO SEGURA DAS TABELAS (SEM APAGAR DADOS)
# ============================================
# db.create_all() cria tabelas novas, mas NÃO adiciona colunas a tabelas
# existentes. Esta função adiciona as colunas que faltam na tabela
# financeiro (banco real antigo), preservando todos os dados.
# Compatível com SQLite (PRAGMA) e PostgreSQL (information_schema).

from sqlalchemy import text


def aplicar_migracoes():
    """
    Adiciona colunas ausentes na tabela financeiro e garante a tabela despesa.
    Idempotente: pode ser executada várias vezes sem efeito colateral.
    Deve ser chamada dentro de app.app_context().
    """
    try:
        db.create_all()

        # Descobre as colunas existentes de forma portátil
        colunas = set()
        if db.engine.dialect.name == "sqlite":
            rows = db.session.execute(text("PRAGMA table_info(financeiro)")).fetchall()
            colunas = {r[1] for r in rows}
        else:  # postgresql / outros
            rows = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'financeiro'"
            )).fetchall()
            colunas = {r[0] for r in rows}

        if "plano_id" not in colunas:
            db.session.execute(text("ALTER TABLE financeiro ADD COLUMN plano_id INTEGER"))
        if "tipo" not in colunas:
            db.session.execute(text(
                "ALTER TABLE financeiro ADD COLUMN tipo VARCHAR(30) DEFAULT 'agendamento'"
            ))
        if "descricao" not in colunas:
            db.session.execute(text(
                "ALTER TABLE financeiro ADD COLUMN descricao VARCHAR(300)"
            ))
        if "taxa_cartao" not in colunas:
            db.session.execute(text(
                "ALTER TABLE financeiro ADD COLUMN taxa_cartao FLOAT DEFAULT 0"
            ))
        if "data_pagamento" not in colunas:
            db.session.execute(text(
                "ALTER TABLE financeiro ADD COLUMN data_pagamento VARCHAR(10)"
            ))

        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass