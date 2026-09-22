# ============================================
# TESTE: DATA DO PAGAMENTO NO FATURAMENTO
# ============================================
# Prova que um agendamento marcado como PAGO entra no faturamento na data em
# que o pagamento foi REGISTRADO (hoje), e não na data do atendimento.
# Antes, um agendamento pago hoje para uma data futura só aparecia no
# Dashboard/Financeiro/PDF quando a data do atendimento chegasse.
# Mesma regra já usada na venda/renovação de plano (data_pagamento = hoje).
#
# Executar: python teste_data_pagamento.py
# Banco: TEMPORÁRIO (teste_data_pagamento_temp.db) — nunca o de produção.

import os
import sys
from datetime import date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
BANCO_TEMP = os.path.join(BASE, "teste_data_pagamento_temp.db")
if os.path.exists(BANCO_TEMP):
    try:
        os.remove(BANCO_TEMP)
    except PermissionError:
        pass

os.environ["DATABASE_URL"] = "sqlite:///" + BANCO_TEMP.replace("\\", "/")
os.environ["APP_ENV"] = "development"
os.environ.pop("RENDER", None)
os.environ.pop("PRODUCTION", None)

RESULTADOS = []


def registrar(nome, resultado, detalhe=""):
    status = "PASS" if resultado else "FAIL"
    RESULTADOS.append((nome, status, detalhe))
    print(f"  [{status}] {nome}" + (f" — {detalhe}" if detalhe else ""))


def rodar():
    from app import create_app
    from models.financeiro import Financeiro
    from services.barbearia_service import (
        buscar_plano_tipo_por_nome,
        buscar_servico_por_nome,
        criar_agendamento,
        criar_cliente,
        criar_plano,
        listar_profissionais,
    )
    from services.financeiro_service import (
        atualizar_pagamento_agendamento,
        calcular_financeiro,
        periodo_para_datas,
    )

    print("=" * 70)
    print("TESTE DA DATA DO PAGAMENTO NO FATURAMENTO (banco temporario)")
    print("=" * 70)

    app = create_app()
    app.config["TESTING"] = True

    hoje = date.today()
    hoje_str = hoje.strftime("%Y-%m-%d")
    data_futura_str = (hoje + timedelta(days=15)).strftime("%Y-%m-%d")

    with app.app_context():
        profissional = listar_profissionais()[0]
        # Valor real do serviço "Corte" conforme a semente do sistema
        valor_corte = float(buscar_servico_por_nome("Corte").preco or 0)
        registrar("Servico 'Corte' com preco cadastrado", valor_corte > 0,
                  f"valor={valor_corte}")

        # ------------------------------------------------------------
        # [1] Agendamento para data FUTURA, pago HOJE
        # ------------------------------------------------------------
        print("\n[1] Agendamento futuro pago hoje entra no faturamento de HOJE")
        ag_futuro = criar_agendamento(
            "Cliente Futuro Pago", "38991380031", data_futura_str, "10:00", "Corte",
            profissional_id=profissional.id,
        )
        financeiro = Financeiro.query.filter_by(agendamento_id=ag_futuro.id).first()
        registrar("Financeiro nasce com o agendamento", financeiro is not None)
        registrar("Nasce pendente (nao entra na receita)",
                  financeiro is not None and financeiro.status == "pendente")

        financeiro, erro = atualizar_pagamento_agendamento(
            ag_futuro.id, "pago", "dinheiro"
        )
        registrar("Pagamento registrado",
                  financeiro is not None and financeiro.status == "pago", erro or "")
        registrar(
            "data_pagamento = HOJE (registro), nao a data do atendimento",
            financeiro is not None and financeiro.data_pagamento == hoje_str,
            f"{financeiro.data_pagamento if financeiro else None} | atendimento={data_futura_str}",
        )

        fin_hoje = calcular_financeiro(*periodo_para_datas("hoje"))
        registrar("Receita entra no faturamento de HOJE",
                  fin_hoje["receita_bruta"] == valor_corte,
                  f"receita_hoje={fin_hoje['receita_bruta']} esperado={valor_corte}")
        registrar("Dashboard de hoje conta 1 receita",
                  fin_hoje["quantidade_receitas"] == 1)
        registrar("Movimentacao listada com a data do pagamento (hoje)",
                  any(m["data"] == hoje_str for m in fin_hoje["movimentacoes"]))

        fin_futuro = calcular_financeiro(data_futura_str, data_futura_str)
        registrar(
            "Nao aparece mais filtrando so pela data do atendimento (futuro)",
            fin_futuro["receita_bruta"] == 0.0,
            f"receita_futuro={fin_futuro['receita_bruta']}",
        )
        fin_mes = calcular_financeiro(*periodo_para_datas("mes"))
        registrar("Aparece no filtro do mes corrente",
                  fin_mes["receita_bruta"] >= valor_corte)

        # ------------------------------------------------------------
        # [2] Agendamento PENDENTE continua fora do faturamento
        # ------------------------------------------------------------
        print("\n[2] Agendamento pendente nao entra no faturamento")
        ag_pend = criar_agendamento(
            "Cliente Pendente", "38991380032", hoje_str, "11:00", "Corte",
            profissional_id=profissional.id,
        )
        fin_pend, erro_pend = atualizar_pagamento_agendamento(
            ag_pend.id, "pendente", ""
        )
        registrar("Pagamento pendente registrado",
                  fin_pend is not None and fin_pend.status == "pendente",
                  erro_pend or "")

        fin_hoje2 = calcular_financeiro(*periodo_para_datas("hoje"))
        registrar("Pendente nao soma na receita de hoje",
                  fin_hoje2["receita_bruta"] == valor_corte,
                  f"receita_hoje={fin_hoje2['receita_bruta']}")
        registrar("Pendente nao aparece nas movimentacoes",
                  all("Cliente Pendente" not in (m.get("descricao") or "")
                      for m in fin_hoje2["movimentacoes"]))
        fin_pend_hoje = calcular_financeiro(hoje_str, hoje_str)
        registrar("Filtro pela data do atendimento do pendente tambem ignora",
                  fin_pend_hoje["receita_bruta"] == valor_corte,
                  f"receita={fin_pend_hoje['receita_bruta']}")

        # ------------------------------------------------------------
        # [3] Reeditar o pagamento NAO duplica o lancamento
        # ------------------------------------------------------------
        print("\n[3] Reeditar o pagamento nao duplica no Financeiro")
        qtd_antes = Financeiro.query.filter_by(agendamento_id=ag_futuro.id).count()
        financeiro2 = None
        for _ in range(3):
            financeiro2, erro2 = atualizar_pagamento_agendamento(
                ag_futuro.id, "pago", "pix"
            )
        qtd_depois = Financeiro.query.filter_by(agendamento_id=ag_futuro.id).count()
        registrar("Um unico lancamento por agendamento",
                  qtd_antes == 1 and qtd_depois == 1, f"{qtd_antes} -> {qtd_depois}")
        registrar("Forma de pagamento atualizada para pix",
                  financeiro2 is not None and financeiro2.forma_pagamento == "pix")
        registrar("data_pagamento continua HOJE",
                  financeiro2 is not None and financeiro2.data_pagamento == hoje_str,
                  financeiro2.data_pagamento if financeiro2 else "")

        fin_hoje3 = calcular_financeiro(*periodo_para_datas("hoje"))
        registrar("Receita de hoje nao duplicou apos reeditar",
                  fin_hoje3["receita_bruta"] == valor_corte,
                  f"receita={fin_hoje3['receita_bruta']}")
        registrar("Total de lancamentos pagos = 1",
                  Financeiro.query.filter_by(status="pago").count() == 1,
                  f"pagos={Financeiro.query.filter_by(status='pago').count()}")

        # Fechar e reabrir o pagamento mantem o lancamento unico
        atualizar_pagamento_agendamento(ag_futuro.id, "pendente", "")
        atualizar_pagamento_agendamento(ag_futuro.id, "pago", "dinheiro")
        registrar("Voltar para pendente e pagar de novo nao duplica",
                  Financeiro.query.filter_by(agendamento_id=ag_futuro.id).count() == 1)
        fin_hoje4 = calcular_financeiro(*periodo_para_datas("hoje"))
        registrar("Receita de hoje segue unica",
                  fin_hoje4["receita_bruta"] == valor_corte,
                  f"receita={fin_hoje4['receita_bruta']}")

        # ------------------------------------------------------------
        # [4] Consistencia com a venda de plano (mesma regra: hoje)
        # ------------------------------------------------------------
        print("\n[4] Venda de plano usa a mesma regra (data de hoje)")
        cliente = criar_cliente(nome="Cliente Plano Data", telefone="38991380033")
        plano = criar_plano(
            cliente_id=cliente.id,
            plano_tipo_id=buscar_plano_tipo_por_nome("Bronze").id,
        )
        fin_plano = Financeiro.query.filter_by(plano_id=plano.id, tipo="plano").first()
        registrar("Venda de plano registrada com data_pagamento = hoje",
                  fin_plano is not None and fin_plano.data_pagamento == hoje_str,
                  fin_plano.data_pagamento if fin_plano else "")
        fin_hoje5 = calcular_financeiro(*periodo_para_datas("hoje"))
        registrar("Faturamento de hoje = agendamento + plano",
                  round(fin_hoje5["receita_bruta"], 2) ==
                  round(valor_corte + float(plano.preco or 0), 2),
                  f"receita={fin_hoje5['receita_bruta']}")
        registrar("Duas receitas hoje (agendamento + plano)",
                  fin_hoje5["quantidade_receitas"] == 2)

    print("\n" + "=" * 70)
    passou = sum(1 for _, status, _ in RESULTADOS if status == "PASS")
    falhou = sum(1 for _, status, _ in RESULTADOS if status == "FAIL")
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
