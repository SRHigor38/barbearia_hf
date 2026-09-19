# ============================================
# TESTES: telefone, nome, status de pagamento e botão de gasto
# ============================================
# Executar: python teste_ajustes_exibicao.py
# Usa banco TEMPORÁRIO e NUNCA modifica o banco real.

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BANCO_TEMP = os.path.join(BASE, "teste_ajustes_temp.db")
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


def rodar():
    from utils import formatar_telefone, normalizar_telefone, normalizar_nome
    from app import create_app
    from models import db
    from models.cliente import Cliente
    from models.despesa import Despesa
    from services.barbearia_service import (
        criar_cliente, criar_agendamento, listar_profissionais,
    )
    from services.financeiro_service import atualizar_pagamento_agendamento

    print("=" * 70)
    print("TESTES DE AJUSTES DE EXIBICAO (banco temporario)")
    print("=" * 70)

    # ------------------------------------------------------------
    # 1) FORMATAÇÃO DE TELEFONE (funções puras)
    # ------------------------------------------------------------
    print("\n[1] Formatacao de telefone")
    registrar("38991388394 -> (38) 99138-8394",
              formatar_telefone("38991388394") == "(38) 99138-8394",
              formatar_telefone("38991388394"))
    registrar("3899138834 -> (38) 9913-8834",
              formatar_telefone("3899138834") == "(38) 9913-8834",
              formatar_telefone("3899138834"))
    registrar("Ja formatado permanece igual",
              formatar_telefone("(38) 99138-8394") == "(38) 99138-8394",
              formatar_telefone("(38) 99138-8394"))
    registrar("+55 38 99138-8394 -> (38) 99138-8394",
              formatar_telefone("+55 38 99138-8394") == "(38) 99138-8394",
              formatar_telefone("+55 38 99138-8394"))
    registrar("DDD 55 nao e confundido com codigo do pais",
              formatar_telefone("55991388394") == "(55) 99138-8394",
              formatar_telefone("55991388394"))
    registrar("Valor invalido nao inventa numero",
              formatar_telefone("123") == "123", formatar_telefone("123"))
    registrar("Armazenamento somente digitos",
              normalizar_telefone("(38) 99138-8394") == "38991388394",
              normalizar_telefone("(38) 99138-8394"))

    # ------------------------------------------------------------
    # 2) NORMALIZAÇÃO DE NOME (funções puras)
    # ------------------------------------------------------------
    print("\n[2] Normalizacao de nome")
    registrar("joao da silva -> Joao da Silva",
              normalizar_nome("joao da silva") == "Joao da Silva",
              normalizar_nome("joao da silva"))
    registrar("JOAO DA SILVA -> Joao da Silva",
              normalizar_nome("JOAO DA SILVA") == "Joao da Silva",
              normalizar_nome("JOAO DA SILVA"))
    registrar("jOaO dA sIlVa -> Joao da Silva",
              normalizar_nome("jOaO dA sIlVa") == "Joao da Silva",
              normalizar_nome("jOaO dA sIlVa"))
    registrar("Espacos extras normalizados",
              normalizar_nome("  maria   clara  ") == "Maria Clara",
              normalizar_nome("  maria   clara  "))

    return _rodar_app(registrar, create_app, db, Cliente, Despesa,
                      criar_cliente, criar_agendamento, listar_profissionais,
                      atualizar_pagamento_agendamento)


def _rodar_app(registrar, create_app, db, Cliente, Despesa,
               criar_cliente, criar_agendamento, listar_profissionais,
               atualizar_pagamento_agendamento):
    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        prof = listar_profissionais()[0]

        cli = criar_cliente(nome="joao da silva", telefone="38991388394")
        registrar("Cliente nome armazenado normalizado",
                  cli.nome == "Joao da Silva", cli.nome)
        registrar("Cliente telefone armazenado so digitos",
                  cli.telefone == "38991388394", cli.telefone)

        cli2 = criar_cliente(nome="joao da silva", telefone="(38) 99138-8394")
        registrar("Busca por telefone formatado nao duplica cliente",
                  cli2.id == cli.id, f"{cli2.id} == {cli.id}")
        registrar("Total de clientes = 1",
                  Cliente.query.count() == 1, Cliente.query.count())

        ag_pend = criar_agendamento(
            "joao da silva", "38991388394", "2026-09-25", "10:00", "Corte",
            profissional_id=prof.id, cliente_id=cli.id,
        )
        registrar("Agendamento nome normalizado",
                  ag_pend.nome == "Joao da Silva", ag_pend.nome)
        registrar("Agendamento telefone so digitos",
                  ag_pend.telefone == "38991388394", ag_pend.telefone)

        ag_pago = criar_agendamento(
            "maria clara", "3899138834", "2026-09-25", "11:00", "Corte",
            profissional_id=prof.id,
        )
        atualizar_pagamento_agendamento(ag_pago.id, "pago", "dinheiro")

    print("\n[3] Pagamento em /admin/agendamentos")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["admin_id"] = 1

    r_ag = client.get("/admin/agendamentos")
    html_ag = r_ag.get_data(as_text=True)
    registrar("Pagina de agendamentos responde 200", r_ag.status_code == 200)
    registrar("Coluna 'Pagamento' presente", "Pagamento" in html_ag)
    registrar("Mostra 'Pendente'", "Pendente" in html_ag)
    registrar("Mostra 'Pago'", "Pago" in html_ag)
    registrar("Mostra 'Pago — Dinheiro'", "— Dinheiro" in html_ag)
    registrar("Telefone formatado (38) 99138-8394", "(38) 99138-8394" in html_ag)
    registrar("Telefone formatado (38) 9913-8834", "(38) 9913-8834" in html_ag)

    print("\n[4] Financeiro x Gastos")
    html_fin = client.get("/admin/financeiro").get_data(as_text=True)
    registrar("Financeiro NAO tem botao 'Cadastrar Gasto'",
              "Cadastrar Gasto" not in html_fin)
    registrar("Financeiro mantem 'Gerar Relatorio PDF'",
              "Gerar Relat" in html_fin)

    r_gastos = client.get("/admin/gastos")
    html_gastos = r_gastos.get_data(as_text=True)
    registrar("/admin/gastos responde 200", r_gastos.status_code == 200)
    registrar("/admin/gastos mantem formulario 'Registrar Gasto'",
              "Registrar Gasto" in html_gastos)

    with app.app_context():
        antes = Despesa.query.count()
    client.post("/admin/gastos", data={
        "descricao": "Teste despesa", "categoria": "Produtos",
        "valor": "50.00", "data": "2026-09-19", "observacao": "",
    })
    with app.app_context():
        depois = Despesa.query.count()
    registrar("Cadastro de despesa via /admin/gastos funciona",
              depois == antes + 1, f"{antes} -> {depois}")

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