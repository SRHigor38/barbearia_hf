# ============================================
# TESTE DA CORREÇÃO: venda de plano sem agendamento
# ============================================
# Executar: python teste_correcao_planos.py
#
# Usa banco TEMPORÁRIO (teste_correcao_temp.db) e NUNCA modifica o banco real.
#
# Etapas:
#   0) Simula base "legada" com financeiro.agendamento_id NOT NULL e confirma
#      que aplicar_migracoes() remove a constraint preservando os dados.
#   1) Plano Bronze R$ 90,00 -> agendamento_id NULL, plano_id, status pago
#   2) Plano VIP   R$ 109,99 -> valor em REAIS (nunca 10999/1099/1.0999/1.09)
#   3) Venda de plano sem agendamento não gera IntegrityError
#   4) Agendamento pago -> agendamento_id preenchido
#   5) Plano + agendamento não se confundem nem duplicam
#   6) Faturamento de planos e do mês incluem a venda
#   7) Lucro líquido = faturamento - despesas (com e sem gasto de 600)
#   8) Renovação gera novo lançamento (agendamento_id NULL, valor em REAIS)

import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BANCO_TEMP = os.path.join(BASE, "teste_correcao_temp.db")
if os.path.exists(BANCO_TEMP):
    try:
        os.remove(BANCO_TEMP)
    except PermissionError:
        pass

os.environ["DATABASE_URL"] = "sqlite:///" + BANCO_TEMP.replace("\\", "/")

RESULTADOS = []


def registrar(nome, resultado, detalhe=""):
    status = "PASS" if resultado else "FAIL"
    RESULTADOS.append((nome, status, detalhe))
    print(f"  [{status}] {nome}" + (f" — {detalhe}" if detalhe else ""))


def _schema_legado_financeiro(con):
    """Reconstrói financeiro como a base antiga: agendamento_id NOT NULL."""
    cur = con.cursor()
    cur.execute("ALTER TABLE financeiro RENAME TO financeiro_moderno")
    cur.execute(
        """
        CREATE TABLE financeiro (
            id INTEGER NOT NULL,
            agendamento_id INTEGER NOT NULL,
            valor INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL,
            forma_pagamento VARCHAR(20),
            criado_em DATETIME,
            plano_id INTEGER,
            tipo VARCHAR(30) DEFAULT 'agendamento',
            descricao VARCHAR(300),
            taxa_cartao FLOAT DEFAULT 0,
            data_pagamento VARCHAR(10),
            PRIMARY KEY (id),
            UNIQUE (agendamento_id),
            FOREIGN KEY(agendamento_id) REFERENCES agendamento (id)
        )
        """
    )
    cur.execute(
        """
        INSERT INTO financeiro (
            id, agendamento_id, plano_id, tipo, descricao, valor,
            taxa_cartao, status, forma_pagamento, data_pagamento, criado_em
        )
        SELECT id, agendamento_id, plano_id, tipo, descricao, valor,
               taxa_cartao, status, forma_pagamento, data_pagamento, criado_em
        FROM financeiro_moderno
        """
    )
    cur.execute("DROP TABLE financeiro_moderno")
    con.commit()


def rodar():
    from app import create_app
    from sqlalchemy import text
    from models import db
    from models.financeiro import Financeiro
    from services.barbearia_service import (
        criar_cliente, criar_plano, buscar_plano_tipo_por_nome,
        criar_agendamento, listar_profissionais, renovar_plano,
    )
    from services.financeiro_service import (
        aplicar_migracoes, calcular_financeiro, faturamento_planos_periodo,
        periodo_para_datas, registrar_despesa, excluir_despesa,
        atualizar_pagamento_agendamento,
    )

    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("TESTE DA CORRECAO: PLANOS SEM AGENDAMENTO (banco temporario)")
        print("=" * 70)

        # ============================================
        # ETAPA 0: SIMULA BASE LEGADA E MIGRA
        # ============================================
        print("\n[ETAPA 0] Migracao da constraint NOT NULL")
        db.session.remove()
        db.engine.dispose()

        con = sqlite3.connect(BANCO_TEMP)
        cur = con.cursor()
        cur.execute(
            "INSERT INTO agendamento (nome, telefone, data, horario, servico) "
            "VALUES ('Legado', '(00) 0000-0000', '2026-09-10', '10:00', 'Corte')"
        )
        ag_legado_id = cur.lastrowid
        _schema_legado_financeiro(con)
        cur.execute(
            "INSERT INTO financeiro (agendamento_id, valor, status, forma_pagamento, "
            "tipo, descricao, taxa_cartao, data_pagamento) "
            "VALUES (?, ?, 'pago', 'dinheiro', 'agendamento', 'Corte - Legado', 0, '2026-09-10')",
            (ag_legado_id, 40),
        )
        con.commit()

        info = {r[1]: r for r in cur.execute("PRAGMA table_info(financeiro)").fetchall()}
        con.close()
        registrar(
            "Base legada tem agendamento_id NOT NULL (setup)",
            info["agendamento_id"][3] == 1,
            f"notnull={info['agendamento_id'][3]}",
        )

        aplicar_migracoes()

        con = sqlite3.connect(BANCO_TEMP)
        cur = con.cursor()
        info = {r[1]: r for r in cur.execute("PRAGMA table_info(financeiro)").fetchall()}
        linha = cur.execute(
            "SELECT agendamento_id, valor, descricao FROM financeiro "
            "WHERE descricao = 'Corte - Legado'"
        ).fetchone()
        con.close()

        registrar(
            "Migracao remove NOT NULL de agendamento_id",
            info["agendamento_id"][3] == 0,
            f"notnull={info['agendamento_id'][3]}",
        )
        registrar(
            "Coluna valor virou FLOAT (REAIS)",
            info["valor"][2].upper() == "FLOAT",
            f"tipo={info['valor'][2]}",
        )
        registrar(
            "Registro financeiro legado preservado",
            linha is not None and linha[0] == ag_legado_id and linha[1] == 40,
            f"linha={linha}",
        )

        db.session.execute(text("DELETE FROM financeiro WHERE descricao = 'Corte - Legado'"))
        db.session.execute(text("DELETE FROM agendamento WHERE nome = 'Legado'"))
        db.session.commit()

        hoje = periodo_para_datas("hoje")[0]
        ini_mes, fim_mes = periodo_para_datas("mes")

        # ============================================
        # TESTE 1: Plano Bronze R$ 90,00
        # ============================================
        print("\n[TESTE 1] Plano Bronze R$ 90,00")
        bronze = buscar_plano_tipo_por_nome("Bronze")
        cli1 = criar_cliente(nome="Cliente Bronze", telefone="(11) 90000-0001")
        plano1 = criar_plano(cliente_id=cli1.id, plano_tipo_id=bronze.id)
        registrar("Plano criado", plano1 is not None)

        fin1 = Financeiro.query.filter_by(plano_id=plano1.id, tipo="plano").first()
        registrar("Financeiro do plano criado", fin1 is not None)
        registrar("plano_id preenchido", fin1 is not None and fin1.plano_id == plano1.id)
        registrar("agendamento_id = NULL", fin1 is not None and fin1.agendamento_id is None)
        registrar("valor = 90.00", fin1 is not None and fin1.valor == 90.0,
                  f"valor={fin1.valor if fin1 else None}")
        registrar("status = pago", fin1 is not None and fin1.status == "pago")
        registrar("data_pagamento = hoje", fin1 is not None and fin1.data_pagamento == hoje,
                  f"data={fin1.data_pagamento if fin1 else None}")

        # ============================================
        # TESTE 3: sem agendamento -> sem IntegrityError
        # ============================================
        print("\n[TESTE 3] Venda de plano sem agendamento nao gera IntegrityError")
        registrar("Plano + financeiro persistidos (sem IntegrityError)",
                  plano1 is not None and fin1 is not None and
                  Financeiro.query.filter_by(plano_id=plano1.id).count() == 1)

        # ============================================
        # TESTE 6: Faturamento de planos / faturamento do mês
        # ============================================
        print("\n[TESTE 6] Faturamento de planos e do mes")
        fat_planos = faturamento_planos_periodo(ini_mes, fim_mes)
        ind_mes = calcular_financeiro(ini_mes, fim_mes)
        registrar("Faturamento de planos do mes = 90.00", fat_planos == 90.0,
                  f"valor={fat_planos}")
        registrar("Faturamento do mes inclui os 90.00", ind_mes["receita_bruta"] == 90.0,
                  f"receita={ind_mes['receita_bruta']}")

        # ============================================
        # TESTE 7: Lucro líquido
        # ============================================
        print("\n[TESTE 7] Lucro liquido")
        registrar("Lucro sem despesas = 90.00", ind_mes["lucro_liquido"] == 90.0,
                  f"lucro={ind_mes['lucro_liquido']}")

        desp, err = registrar_despesa("Aluguel teste", "Aluguel", 600.0, hoje)
        ind_com_desp = calcular_financeiro(ini_mes, fim_mes)
        registrar("Lucro com despesa 600 = -510.00",
                  ind_com_desp["lucro_liquido"] == -510.0,
                  f"lucro={ind_com_desp['lucro_liquido']} (nao pode ser -600.00)")
        registrar("Despesa nao substitui o faturamento",
                  ind_com_desp["receita_bruta"] == 90.0,
                  f"receita={ind_com_desp['receita_bruta']}")
        if desp:
            excluir_despesa(desp.id)

        # ============================================
        # TESTE 2: Plano VIP R$ 109,99
        # ============================================
        print("\n[TESTE 2] Plano VIP R$ 109,99")
        vip = buscar_plano_tipo_por_nome("VIP")
        cli2 = criar_cliente(nome="Cliente VIP", telefone="(11) 90000-0002")
        plano2 = criar_plano(cliente_id=cli2.id, plano_tipo_id=vip.id)
        fin2 = Financeiro.query.filter_by(plano_id=plano2.id, tipo="plano").first()
        registrar("valor = 109.99", fin2 is not None and fin2.valor == 109.99,
                  f"valor={fin2.valor if fin2 else None}")
        registrar("NAO esta em centavos (nem 10999/1099/1.0999/1.09)",
                  fin2 is not None and fin2.valor not in (10999.0, 1099.0, 1.0999, 1.09),
                  f"valor={fin2.valor if fin2 else None}")
        registrar("agendamento_id = NULL (VIP)",
                  fin2 is not None and fin2.agendamento_id is None)

        # ============================================
        # TESTE 4: Agendamento pago
        # ============================================
        print("\n[TESTE 4] Agendamento pago")
        prof = listar_profissionais()[0]
        ag = criar_agendamento(
            nome="Cliente Normal", telefone="(11) 90000-0004",
            data="2026-09-20", horario="10:00", servico="Corte",
            profissional_id=prof.id,
        )
        _, err = atualizar_pagamento_agendamento(ag.id, "pago", "pix")
        fin_ag = Financeiro.query.filter_by(agendamento_id=ag.id).first()
        registrar("agendamento_id preenchido",
                  fin_ag is not None and fin_ag.agendamento_id == ag.id)
        registrar("valor do agendamento = 40.00 (REAIS)",
                  fin_ag is not None and fin_ag.valor == 40.0,
                  f"valor={fin_ag.valor if fin_ag else None}")
        registrar("plano_id NULL no agendamento",
                  fin_ag is not None and fin_ag.plano_id is None)

        # ============================================
        # TESTE 5: Plano + agendamento sem duplicidade
        # ============================================
        print("\n[TESTE 5] Plano e agendamento sem duplicidade")
        venda_plano = Financeiro.query.filter_by(plano_id=plano1.id).all()
        registrar("Apenas 1 lancamento ligado ao plano", len(venda_plano) == 1,
                  f"qtd={len(venda_plano)}")
        registrar("Lancamento do plano nao tem agendamento",
                  venda_plano[0].agendamento_id is None)
        registrar("Total de lancamentos distintos",
                  Financeiro.query.count() == 3,
                  f"total={Financeiro.query.count()} (Bronze, VIP, agendamento)")

        # ============================================
        # TESTE 8: Renovação
        # ============================================
        print("\n[TESTE 8] Renovacao de plano")
        renovar_plano(plano2.id, forma_pagamento="cartao", taxa_cartao=2.0)
        renov = Financeiro.query.filter_by(plano_id=plano2.id, tipo="renovacao_plano").first()
        registrar("Renovacao gera lancamento", renov is not None)
        registrar("agendamento_id NULL na renovacao",
                  renov is not None and renov.agendamento_id is None)
        registrar("valor renovacao = 109.99", renov is not None and renov.valor == 109.99,
                  f"valor={renov.valor if renov else None}")
        registrar("taxa cartao registrada = 2.00",
                  renov is not None and renov.taxa_cartao == 2.0,
                  f"taxa={renov.taxa_cartao if renov else None}")
        fat_planos2 = faturamento_planos_periodo(ini_mes, fim_mes)
        registrar("Faturamento de planos soma venda + renovacao (309.98)",
                  abs(fat_planos2 - 309.98) < 0.001, f"valor={fat_planos2}")

        # Resumo
        print("\n" + "=" * 70)
        passou = sum(1 for _, s, _ in RESULTADOS if s == "PASS")
        falhou = sum(1 for _, s, _ in RESULTADOS if s == "FAIL")
        print(f"TOTAL: {passou} PASS / {falhou} FAIL / {len(RESULTADOS)} testes")
        return falhou == 0, passou, falhou


if __name__ == "__main__":
    ok, p, f = rodar()
    print(f"\nRESULTADO GERAL: {'APROVADO' if ok else 'COM FALHAS'} ({p} PASS / {f} FAIL)")
    try:
        if os.path.exists(BANCO_TEMP):
            os.remove(BANCO_TEMP)
    except PermissionError:
        pass
    sys.exit(0 if ok else 1)
