# ============================================
# TESTE: EXCLUSÃO DOS DADOS DO CLIENTE (LGPD)
# ============================================
# Lei 13.709/2018 (LGPD), art. 18, VI — direito de eliminação dos dados.
# Prova que POST /admin/clientes/excluir/<id> remove, em UMA transação:
#   - os agendamentos do cliente (e o financeiro de cada um);
#   - o plano do cliente (benefícios + histórico de venda/renovação);
#   - o próprio cliente.
# E que NADA de outro cliente é afetado.
#
# Executar: python teste_lgpd_exclusao_cliente.py
# Banco: TEMPORÁRIO (teste_lgpd_temp.db) — nunca o de produção.

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BANCO_TEMP = os.path.join(BASE, "teste_lgpd_temp.db")
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
    from datetime import datetime, timedelta

    from app import create_app
    from models.admin import Admin
    from models.agendamento import Agendamento
    from models.agendamento_servico import AgendamentoServico
    from models.cliente import Cliente
    from models.financeiro import Financeiro
    from models.plano import Plano
    from models.plano_beneficio import PlanoBeneficio
    from services.barbearia_service import (
        buscar_plano_tipo_por_nome,
        criar_agendamento,
        criar_agendamento_plano,
        criar_cliente,
        criar_plano,
        listar_profissionais,
        renovar_plano,
    )
    from services.financeiro_service import atualizar_pagamento_agendamento

    print("=" * 70)
    print("TESTE DE EXCLUSAO DE DADOS DO CLIENTE (LGPD) — banco temporario")
    print("=" * 70)

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # permite o POST direto no teste

    TELEFONE = "38991380099"
    TELEFONE_OUTRO = "38991380011"
    TELEFONE_VAZIO = "38991380000"
    TELEFONE_PLANO = "38991380077"  # cliente do fluxo da tela de Planos

    # ------------------------------------------------------------
    # Massa de dados: cliente LGPD com agendamento pago + plano + renovação
    # e um OUTRO cliente que não pode ser afetado.
    # ------------------------------------------------------------
    with app.app_context():
        admin = Admin.query.first()
        admin_id = admin.id if admin else 1
        profissional = listar_profissionais()[0]

        cliente = criar_cliente(nome="Cliente Lgpd", telefone=TELEFONE)
        plano = criar_plano(
            cliente_id=cliente.id,
            plano_tipo_id=buscar_plano_tipo_por_nome("Bronze").id,
            dias_permitidos="1,2,3,4,5,6,7",
        )
        registrar(
            "Cliente e plano ativo criados",
            cliente is not None and plano is not None,
        )

        # Agendamento normal PAGO (gera financeiro com status "pago")
        agendamento_pago = criar_agendamento(
            "Cliente Lgpd", TELEFONE, "2026-10-01", "10:00", "Corte",
            profissional_id=profissional.id, cliente_id=cliente.id,
        )
        atualizar_pagamento_agendamento(agendamento_pago.id, "pago", "dinheiro")
        fin_agendamento = Financeiro.query.filter_by(
            agendamento_id=agendamento_pago.id
        ).first()
        registrar(
            "Agendamento pago com financeiro",
            fin_agendamento is not None and fin_agendamento.status == "pago",
        )

        # Agendamento do plano (multi-serviço: consome benefícios)
        data_plano = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        agendamento_plano, erro = criar_agendamento_plano(
            cliente_id=cliente.id,
            plano_id=plano.id,
            data=data_plano,
            horario="14:00",
            profissional_id=profissional.id,
        )
        registrar("Agendamento do plano criado", agendamento_plano is not None, erro or "")
        registrar(
            "Agendamento do plano possui servicos vinculados",
            agendamento_plano is not None
            and AgendamentoServico.query.filter_by(
                agendamento_id=agendamento_plano.id
            ).count() > 0,
        )

        # Histórico de renovação (financeiro tipo "renovacao_plano")
        registrar("Plano renovado (historico financeiro)",
                  renovar_plano(plano.id) is not None)

        # Outro cliente, que deve permanecer intacto
        outro_cliente = criar_cliente(nome="Outro Cliente", telefone=TELEFONE_OUTRO)
        outro_agendamento = criar_agendamento(
            "Outro Cliente", TELEFONE_OUTRO, "2026-10-02", "09:00", "Barba",
            profissional_id=profissional.id, cliente_id=outro_cliente.id,
        )

        ids = {
            "cliente": cliente.id,
            "plano": plano.id,
            "agendamento_pago": agendamento_pago.id,
            "agendamento_plano": agendamento_plano.id if agendamento_plano else -1,
            "outro_cliente": outro_cliente.id,
            "outro_agendamento": outro_agendamento.id,
        }

        qtd_fin_plano = Financeiro.query.filter_by(plano_id=plano.id).count()
        registrar(
            "Financeiro do plano (venda + renovacao) gravado",
            qtd_fin_plano >= 2,
            f"qtd={qtd_fin_plano}",
        )
        registrar("Beneficios do plano existem",
                  PlanoBeneficio.query.filter_by(plano_id=plano.id).count() > 0)

    client = app.test_client()

    # ------------------------------------------------------------
    # 1) Proteção: a rota exige login
    # ------------------------------------------------------------
    print("\n[1] A rota exige login (login_necessario)")
    sem_login = client.post(f"/admin/clientes/excluir/{ids['cliente']}")
    with app.app_context():
        ainda_existe = Cliente.query.get(ids["cliente"]) is not None
    destino = sem_login.headers.get("Location", "")
    registrar(
        "POST sem login redireciona para /admin/login",
        sem_login.status_code == 302 and "/admin/login" in destino,
        f"status={sem_login.status_code} destino={destino}",
    )
    registrar("Sem login nenhum dado e excluido", ainda_existe)

    # Login do admin
    with client.session_transaction() as sessao:
        sessao["admin_id"] = admin_id
        sessao["admin_usuario"] = "admin"

    # ------------------------------------------------------------
    # 2) Cliente inexistente: flash de erro e nada é removido
    # ------------------------------------------------------------
    print("\n[2] Cliente inexistente nao remove nada")
    resposta = client.post("/admin/clientes/excluir/999999")
    with app.app_context():
        registrar("Cliente inexistente responde 302", resposta.status_code == 302)
        registrar("Cliente real permanece no banco",
                  Cliente.query.get(ids["cliente"]) is not None)
        registrar("Plano real permanece no banco",
                  Plano.query.get(ids["plano"]) is not None)

    # ------------------------------------------------------------
    # 3) Botão "Excluir cliente (LGPD)" na lista de agendamentos
    # ------------------------------------------------------------
    print("\n[3] Botao LGPD na lista de agendamentos (filtro por telefone)")
    html = client.get(f"/admin/agendamentos?telefone={TELEFONE}").get_data(as_text=True)
    registrar("Lista responde 200 com o filtro de telefone",
              client.get(f"/admin/agendamentos?telefone={TELEFONE}").status_code == 200)
    registrar("Mostra o botao 'Excluir cliente (LGPD)'",
              "Excluir cliente (LGPD)" in html)
    registrar("Formulario aponta para a rota da LGPD",
              f"/admin/clientes/excluir/{ids['cliente']}" in html)
    registrar("Exige confirmacao antes de excluir",
              "Excluir este cliente (LGPD)" in html)

    html_sem = client.get(f"/admin/agendamentos?telefone={TELEFONE_VAZIO}").get_data(as_text=True)
    registrar("Sem cliente cadastrado o botao nao aparece",
              "Excluir cliente (LGPD)" not in html_sem)

    html_outro = client.get(f"/admin/agendamentos?telefone={TELEFONE_OUTRO}").get_data(as_text=True)
    registrar("Filtro por telefone traz o cliente correto",
              f"/admin/clientes/excluir/{ids['outro_cliente']}" in html_outro
              and f"/admin/clientes/excluir/{ids['cliente']}" not in html_outro)

    # ------------------------------------------------------------
    # 4) Exclusão completa via rota (fluxo real da LGPD)
    # ------------------------------------------------------------
    print("\n[4] Exclusao do cliente via POST /admin/clientes/excluir/<id>")
    resposta = client.post(
        f"/admin/clientes/excluir/{ids['cliente']}", follow_redirects=True
    )
    html_resposta = resposta.get_data(as_text=True)
    registrar("Rota responde 200 apos o redirect", resposta.status_code == 200)
    registrar("Flash confirma os agendamentos removidos",
              "2 agendamento(s)" in html_resposta)
    registrar("Flash confirma o plano removido", "1 plano(s)" in html_resposta)
    registrar("Sem mensagem de erro interno",
              "Erro interno do servidor" not in html_resposta)

    # ------------------------------------------------------------
    # 5) Tudo foi realmente removido do banco
    # ------------------------------------------------------------
    print("\n[5] Cliente, Agendamento, Financeiro e Plano sumiram do banco")
    with app.app_context():
        registrar("Cliente removido",
                  Cliente.query.get(ids["cliente"]) is None)
        registrar("Plano removido",
                  Plano.query.get(ids["plano"]) is None)
        registrar("Agendamento pago removido",
                  Agendamento.query.get(ids["agendamento_pago"]) is None)
        registrar("Agendamento do plano removido",
                  Agendamento.query.get(ids["agendamento_plano"]) is None)
        registrar("Nenhum agendamento ligado ao cliente",
                  Agendamento.query.filter_by(cliente_id=ids["cliente"]).count() == 0)
        registrar("Nenhum agendamento ligado ao plano",
                  Agendamento.query.filter_by(plano_id=ids["plano"]).count() == 0)
        registrar("Financeiro do agendamento removido",
                  Financeiro.query.filter_by(
                      agendamento_id=ids["agendamento_pago"]).count() == 0)
        registrar("Financeiro do plano (venda + renovacao) removido",
                  Financeiro.query.filter_by(plano_id=ids["plano"]).count() == 0)
        registrar("Beneficios do plano removidos",
                  PlanoBeneficio.query.filter_by(plano_id=ids["plano"]).count() == 0)
        registrar("Vinculos agendamento_servico removidos",
                  AgendamentoServico.query.filter(
                      AgendamentoServico.agendamento_id.in_(
                          [ids["agendamento_pago"], ids["agendamento_plano"]]
                      )
                  ).count() == 0)
        registrar("Nenhum cliente sobrou no banco",
                  Cliente.query.count() == 1,
                  f"clientes={Cliente.query.count()}")

    # ------------------------------------------------------------
    # 6) Nenhum dado de OUTRO cliente foi afetado
    # ------------------------------------------------------------
    print("\n[6] Dados de outro cliente permanecem intactos")
    with app.app_context():
        registrar("Outro cliente continua no banco",
                  Cliente.query.get(ids["outro_cliente"]) is not None)
        registrar("Agendamento do outro cliente continua no banco",
                  Agendamento.query.get(ids["outro_agendamento"]) is not None)
        registrar("Financeiro do outro cliente continua no banco",
                  Financeiro.query.filter_by(
                      agendamento_id=ids["outro_agendamento"]).count() == 1)

    # ------------------------------------------------------------
    # 7) Fluxo da tela /admin/planos (botão ao lado de "Cancelar")
    # ------------------------------------------------------------
    print("\n[7] Exclusao disparada a partir de /admin/planos")
    with app.app_context():
        profissional_plano = listar_profissionais()[0]
        cliente_plano = criar_cliente(
            nome="Cliente Plano Lgpd", telefone=TELEFONE_PLANO
        )
        plano_lgpd = criar_plano(
            cliente_id=cliente_plano.id,
            plano_tipo_id=buscar_plano_tipo_por_nome("Light").id,
            dias_permitidos="1,2,3,4,5,6,7",
        )
        data_agendamento = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
        ag_plano, erro_plano = criar_agendamento_plano(
            cliente_id=cliente_plano.id,
            plano_id=plano_lgpd.id,
            data=data_agendamento,
            horario="16:00",
            profissional_id=profissional_plano.id,
        )
        ids_planos = {
            "cliente": cliente_plano.id,
            "plano": plano_lgpd.id,
            "agendamento": ag_plano.id if ag_plano else -1,
        }
        registrar("Cliente com plano e agendamento criado (fluxo de Planos)",
                  cliente_plano is not None and plano_lgpd is not None
                  and ag_plano is not None, erro_plano or "")

    pagina_planos = client.get("/admin/planos")
    html_planos = pagina_planos.get_data(as_text=True)
    registrar("/admin/planos responde 200", pagina_planos.status_code == 200)
    registrar("Botao 'Excluir cliente (LGPD)' aparece na lista de planos",
              "Excluir cliente (LGPD)" in html_planos)
    registrar("Form aponta para a rota que JA existe",
              f"/admin/clientes/excluir/{ids_planos['cliente']}" in html_planos,
              f"esperado=/admin/clientes/excluir/{ids_planos['cliente']}")
    registrar("Nenhuma rota nova de exclusao foi criada em Planos",
              "/admin/planos/excluir" not in html_planos)
    registrar("'Cancelar' continua na mesma tela",
              f"/admin/planos/cancelar/{ids_planos['plano']}" in html_planos)
    registrar("Confirmacao avisa que e irreversivel e apaga o plano",
              "IRREVERSIVEL" in html_planos
              and "apagar o CADASTRO do cliente" in html_planos
              and "plano dele" in html_planos)
    registrar("Acoes visualmente distintas (LGPD x Cancelar)",
              "btn-lgpd-custom" in html_planos
              and 'class="btn-danger-custom"' in html_planos)
    registrar("LGPD usa icone diferente do Cancelar (shield vs x-circle)",
              "bi-shield-exclamation" in html_planos
              and "bi-x-circle" in html_planos)

    resposta_planos = client.post(
        f"/admin/clientes/excluir/{ids_planos['cliente']}", follow_redirects=True
    )
    registrar("POST a partir do fluxo de Planos responde 200",
              resposta_planos.status_code == 200)
    with app.app_context():
        registrar("Cliente do plano removido",
                  Cliente.query.get(ids_planos["cliente"]) is None)
        registrar("Plano removido",
                  Plano.query.get(ids_planos["plano"]) is None)
        registrar("Agendamento do plano removido",
                  Agendamento.query.get(ids_planos["agendamento"]) is None)
        registrar("Financeiro do plano removido",
                  Financeiro.query.filter_by(
                      plano_id=ids_planos["plano"]).count() == 0)
        registrar("Cliente do passo 6 nao foi afetado",
                  Cliente.query.get(ids["outro_cliente"]) is not None)

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

