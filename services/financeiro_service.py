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
#   plano_tipo.preco       -> REAIS (Float; ex: 90.00 = R$ 90,00)
#
# LUCRO LÍQUIDO = RECEITA BRUTA - DESPESAS(GASTOS + TAXAS)
# Somente financeiro.status == "pago" entra na receita.

import os
import shutil
from datetime import datetime, date, timedelta
from models import db
from models.financeiro import Financeiro
from models.despesa import Despesa
from models.plano_tipo import PlanoTipo
from models.plano import Plano

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
    """Retorna el precio del plan en REAIS (plano_tipo.preco ya está en reais)."""
    if plano_tipo is None:
        return 0.0
    try:
        return round(float(plano_tipo.preco or 0), 2)
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


def faturamento_planos_periodo(data_inicio=None, data_fim=None):
    """
    Faturamento REAL de planos no período: soma apenas lançamentos financeiros
    de vendas (tipo='plano') e renovações (tipo='renovacao_plano') com status
    'pago'. NÃO é a carteira de planos ativos; é o que efetivamente gerou receita.
    Fonte única: tabela financeiro.
    """
    total = 0.0
    for reg, _ in _filtrar_financeiro(data_inicio, data_fim, status="pago"):
        if reg.tipo in ("plano", "renovacao_plano"):
            total += reg.valor or 0
    return round(total, 2)


def valor_carteira_planos():
    """
    Valor total dos planos cadastrados (carteira/contratos), em REAIS.
    Soma o preço de todos os planos de clientes (plano.preco).
    Não representa faturamento realizado — apenas o valor contratado.
    """
    total = 0.0
    for pl in Plano.query.all():
        total += float(pl.preco or 0)
    return round(total, 2)


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


# ============================================
# MIGRACIÓN ESTRUCTURAL: financeiro.agendamento_id NULL
# ============================================
# El modelo y el catálogo ya soportan agendamento_id opcional, pero una base
# creada por una versión anterior conserva "agendamento_id NOT NULL".
# db.create_all() NO altera tablas existentes; por eso hay que reconstruir la
# tabla (patrón oficial de SQLite para cambiar constraints) preservando TODOS
# los datos. Esto permite convivir con dos tipos de lançamento:
#   - Agendamento: agendamento_id = id válido, plano_id = NULL
#   - Venta/renovación de plano: agendamento_id = NULL, plano_id = id válido


def _sqlite_financeiro_agendamento_not_null():
    """True si financeiro (SQLite) todavía tiene agendamento_id NOT NULL."""
    if db.engine.dialect.name != "sqlite":
        return False
    rows = db.session.execute(text("PRAGMA table_info(financeiro)")).fetchall()
    for r in rows:
        if r[1] == "agendamento_id":
            return bool(r[3])  # 1 = NOT NULL, 0 = nullable
    return False


def _backup_sqlite_antes_migracao():
    """Copia el archivo .db a un backup con marca de tiempo (solo SQLite)."""
    if db.engine.dialect.name != "sqlite":
        return None
    caminho = db.engine.url.database
    if not caminho or not os.path.exists(caminho):
        return None
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = "%s.backup_%s" % (caminho, marca)
    shutil.copy2(caminho, destino)
    return destino


def _recriar_financeiro_sqlite():
    """
    Reconstruye la tabla financeiro permitiendo agendamento_id NULL,
    preservando ids, filas, plano_id, tipo, valor, status, formas y fechas.
    Idempotente: solo se invoca cuando la constraint NOT NULL todavía existe.
    Se ejecuta dentro de la transacción de aplicar_migracoes() (rollback seguro).
    """
    db.session.execute(text("ALTER TABLE financeiro RENAME TO financeiro_legado"))
    db.session.execute(text(
        """
        CREATE TABLE financeiro (
            id INTEGER NOT NULL,
            agendamento_id INTEGER,
            plano_id INTEGER,
            tipo VARCHAR(30) NOT NULL DEFAULT 'agendamento',
            descricao VARCHAR(300),
            valor FLOAT NOT NULL DEFAULT 0,
            taxa_cartao FLOAT NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'pendente',
            forma_pagamento VARCHAR(20),
            data_pagamento VARCHAR(10),
            criado_em DATETIME,
            PRIMARY KEY (id),
            UNIQUE (agendamento_id),
            FOREIGN KEY(agendamento_id) REFERENCES agendamento (id),
            FOREIGN KEY(plano_id) REFERENCES plano (id)
        )
        """
    ))
    db.session.execute(text(
        """
        INSERT INTO financeiro (
            id, agendamento_id, plano_id, tipo, descricao, valor,
            taxa_cartao, status, forma_pagamento, data_pagamento, criado_em
        )
        SELECT
            id,
            agendamento_id,
            plano_id,
            COALESCE(tipo, 'agendamento'),
            descricao,
            COALESCE(valor, 0),
            COALESCE(taxa_cartao, 0),
            COALESCE(status, 'pendente'),
            forma_pagamento,
            data_pagamento,
            criado_em
        FROM financeiro_legado
        """
    ))
    db.session.execute(text("DROP TABLE financeiro_legado"))
    # Descarta cualquier objeto ORM cacheado con el esquema anterior
    db.session.expire_all()


def _remover_not_null_agendamento():
    """
    Garantiza que financeiro.agendamento_id acepte NULL en cualquier motor.
    - SQLite: reconstruye la tabla preservando datos.
    - PostgreSQL: ALTER COLUMN ... DROP NOT NULL (solo si aún es NOT NULL).
    """
    if db.engine.dialect.name == "sqlite":
        if _sqlite_financeiro_agendamento_not_null():
            backup = _backup_sqlite_antes_migracao()
            if backup:
                print("Backup criado antes da migração: %s" % backup)
            _recriar_financeiro_sqlite()
        return

    row = db.session.execute(text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'financeiro' AND column_name = 'agendamento_id'"
    )).fetchone()
    if row and str(row[0]).upper() == "NO":
        db.session.execute(text(
            "ALTER TABLE financeiro ALTER COLUMN agendamento_id DROP NOT NULL"
        ))


def aplicar_migracoes():
    """
    Adiciona colunas ausentes na tabela financeiro e garante a tabela despesa.
    Também remove a constraint NOT NULL de financeiro.agendamento_id quando a
    base foi criada por uma versão antiga (venda de plano sem agendamento).
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

        # ============================================
        # ESTRUCTURA: permitir agendamento_id NULL
        # ============================================
        # Venta/renovación de planos NO tiene agendamento asociado.
        # Reconstruye la tabla solo si la constraint NOT NULL todavía existe.
        _remover_not_null_agendamento()

        # ============================================
        # MIGRACIÓN DE PRECIOS A REAIS (DEFINITIVA)
        # ============================================
        # Antes coexistían dos unidades:
        #   - plano.preco       REAIS (90)  en algunos planes de clientes
        #   - plano_tipo.preco  CENTAVOS (9000/10999) en el catálogo
        # Estrategia segura e idempotente:
        #   - Si un importe >= 1000, era CENTAVOS  →  se divide entre 100.
        #   - Si un importe <= 109.99, ya es REAIS →  no se toca.
        # Valores oficiales: 70.00 a 109.99. Ningún precio real supera 109.99.
        try:
            # plano_tipo.preco (catálogo)
            for pt in PlanoTipo.query.all():
                if pt.preco is not None and pt.preco >= 1000:
                    pt.preco = round(float(pt.preco) / 100.0, 2)

            # plano.preco (plan de cada cliente)
            for pl in Plano.query.all():
                if pl.preco is not None and pl.preco >= 1000:
                    pl.preco = round(float(pl.preco) / 100.0, 2)

            # financeiro.valor de ventas/renovaciones que quedaron en centavos
            for f in Financeiro.query.filter(
                Financeiro.tipo.in_(["plano", "renovacao_plano"])
            ).all():
                if f.valor is not None and f.valor >= 1000:
                    f.valor = round(float(f.valor) / 100.0, 2)

            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass